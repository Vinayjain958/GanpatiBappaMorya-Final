#!/bin/sh
# Container start: apply migrations, optionally seed, then serve.
#
# Seeding is opt-in via env vars because Render's free plan has no shell or
# pre-deploy command. Turn a flag on for ONE deploy, then back off:
#   SEED_ON_STARTUP=true              -> seed.py + catalog add-on + demo hours
#   INDEX_EMBEDDINGS_ON_STARTUP=true  -> index_embeddings.py --only-missing
#                                        (calls Gemini once per experience)
# Seeding runs in the background so uvicorn binds $PORT immediately and the
# platform health check does not time out on a long seed.
set -e

cd /app

python -c "from urllib.parse import urlsplit; from src.core.config import get_settings; u = urlsplit(get_settings().database_url); print('[entrypoint] database:', u.scheme, u.username, '@', u.hostname, ':', u.port)" || true

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

# Create/update the ADMIN account only when both credentials are provided
# (never auto-generate a password that would be lost in the deploy log).
if [ -n "$ADMIN_SEED_EMAIL" ] && [ -n "$ADMIN_SEED_PASSWORD" ]; then
  echo "[entrypoint] ensuring admin account"
  python scripts/create_admin.py || echo "[entrypoint] create_admin.py failed (continuing)"
fi

if [ "$SEED_ON_STARTUP" = "true" ] || [ "$INDEX_EMBEDDINGS_ON_STARTUP" = "true" ]; then
  (
    set -e
    if [ "$SEED_ON_STARTUP" = "true" ]; then
      echo "[entrypoint] seeding catalog"
      python scripts/seed.py
      python scripts/import_overture_catalog_addon.py --apply
      python scripts/seed_demo_opening_hours.py
    fi
    if [ "$INDEX_EMBEDDINGS_ON_STARTUP" = "true" ]; then
      echo "[entrypoint] indexing embeddings"
      python scripts/index_embeddings.py --only-missing
    fi
    echo "[entrypoint] background seeding finished"
  ) &
fi

exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
