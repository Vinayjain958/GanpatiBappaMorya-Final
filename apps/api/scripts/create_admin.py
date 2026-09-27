"""Create (or update) a single ADMIN user for local development.

ADMIN accounts can never be created through /api/v1/auth/register — this
explicit, human-run script is the only way to create one, and it always
reads credentials from the environment, never from source code
(docs/AI_CONTEXT.md — no hardcoded credentials).

Usage:
    cd apps/api
    ADMIN_SEED_EMAIL=admin@example.com ADMIN_SEED_PASSWORD='...' python scripts/create_admin.py

Or set ADMIN_SEED_EMAIL / ADMIN_SEED_PASSWORD in .env before running.
If ADMIN_SEED_PASSWORD is omitted, a random password is generated and
printed once (it is not recoverable afterwards).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import get_settings  # noqa: E402
from src.core.db import async_session_factory, engine  # noqa: E402
from src.core.security import generate_dev_password, hash_password  # noqa: E402
from src.models import User  # noqa: E402
from src.repositories.user_repository import UserRepository  # noqa: E402


async def main() -> None:
    settings = get_settings()
    email = settings.admin_seed_email.strip().lower()
    if not email:
        raise SystemExit("ADMIN_SEED_EMAIL is not set — refusing to create an admin without one.")

    password = settings.admin_seed_password
    generated = False
    if not password:
        password = generate_dev_password()
        generated = True

    async with async_session_factory() as session:
        repo = UserRepository(session)
        existing = await repo.get_by_email(email)
        if existing is not None:
            existing.password_hash = hash_password(password)
            existing.role = "admin"
            existing.is_active = True
            await session.commit()
            print(f"Updated existing admin user: {email}")
        else:
            user = User(email=email, password_hash=hash_password(password), role="admin", is_active=True)
            repo.add(user)
            await session.commit()
            print(f"Created admin user: {email}")

    if generated:
        print(f"Generated password (shown once): {password}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
