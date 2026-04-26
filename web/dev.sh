#!/usr/bin/env bash
# Start FastAPI + Vite dev servers with a single command.
# Usage: bash web/dev.sh (from repo root)
set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$REPO_ROOT/web/ui"
npx concurrently \
  --names "api,ui" \
  --prefix-colors "blue,green" \
  "cd \"$REPO_ROOT\" && uvicorn web.api.main:app --reload --port 8000" \
  "npm run dev"
