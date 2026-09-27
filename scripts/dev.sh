#!/usr/bin/env bash
# Starts the LocaLens frontend and backend dev servers together.
# Usage: ./scripts/dev.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

(cd "$ROOT_DIR/apps/api" && source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate; uvicorn src.main:app --reload --port 8000) &
API_PID=$!

(cd "$ROOT_DIR/apps/web" && npm run dev) &
WEB_PID=$!

echo "API:  http://localhost:8000/api/v1/health"
echo "Web:  http://localhost:3000"

trap "kill $API_PID $WEB_PID" EXIT
wait
