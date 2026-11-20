#!/usr/bin/env bash
# Start the backend (port 8000) and the frontend (port 5173). Ctrl+C stops both.
# Usage:  bash scripts/dev.sh        (Git Bash, macOS or Linux)
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

[ -d "$root/backend/.venv" ] || (cd "$root/backend" && uv sync)
[ -d "$root/frontend/node_modules" ] || (cd "$root/frontend" && npm install)

(cd "$root/backend" && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app) &
backend_pid=$!
(cd "$root/frontend" && npm run dev) &
frontend_pid=$!
trap 'kill "$backend_pid" "$frontend_pid" 2>/dev/null || true' EXIT INT TERM

echo "Backend:  http://localhost:8000/health   (docs: http://localhost:8000/docs)"
echo "Frontend: http://localhost:5173"
wait
