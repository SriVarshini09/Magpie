# PIPELINE MODE: the real pipeline on mock services (no keys; public GitHub READMEs are read keylessly), plus the frontend.
# Backend on port 8000, frontend on 5173, in two new PowerShell windows. Close them to stop.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\dev-pipeline.ps1
# Real: intake (keyword router), agent tools, rules, optimizer, guard, cart, signing, chain, Verify, SQLite.
# Mock (labelled simulated, "Mock stores" badge): stores, reference search, SIE, Cognee, Stripe. Offline GitHub: backend/scripts/dev_pipeline.py --github mock.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

if (-not (Test-Path (Join-Path $backendDir ".venv"))) {
    Write-Host "backend: uv sync"
    Push-Location $backendDir; uv sync; Pop-Location
}
if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Host "frontend: npm install"
    Push-Location $frontendDir; npm install; Pop-Location
}

$backend = "Set-Location -LiteralPath '$backendDir'; uv run python scripts/dev_pipeline.py --port 8000 --reload"
$frontend = "Set-Location -LiteralPath '$frontendDir'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backend
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontend

Write-Host "Backend (pipeline mode): http://localhost:8000/health"
Write-Host "Frontend:                http://localhost:5173"
