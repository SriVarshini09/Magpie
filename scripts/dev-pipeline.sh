#!/usr/bin/env bash
# PIPELINE MODE: the real pipeline on mock services (no keys; public GitHub READMEs are read keylessly), plus the frontend. Ctrl+C stops both.
# Usage:  bash scripts/dev-pipeline.sh        (Git Bash, macOS or Linux)
# Real: intake (keyword router), agent tools, rules, optimizer, guard, cart, signing, chain, Verify, SQLite.
# Mock (labelled simulated, "Mock stores" badge): stores, reference search, SIE, Cognee, Stripe. Offline GitHub: backend/scripts/dev_pipeline.py --github mock.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

[ -d "$root/backend/.venv" ] || (cd "$root/backend" && uv sync)
[ -d "$root/frontend/node_modules" ] || (cd "$root/frontend" && npm install)

(cd "$root/backend" && uv run python scripts/dev_pipeline.py --port 8000 --reload) &
backend_pid=$!
(cd "$root/frontend" && npm run dev) &
frontend_pid=$!
trap 'kill "$backend_pid" "$frontend_pid" 2>/dev/null || true' EXIT INT TERM

echo "Backend (pipeline mode): http://localhost:8000/health"
echo "Frontend:                http://localhost:5173"
wait
