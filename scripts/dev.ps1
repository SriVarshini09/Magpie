# Start the backend (port 8000) and the frontend (port 5173) in two new PowerShell windows.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
# Mock mode is the default (DEMO_MODE in .env). Close the two windows to stop.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path (Join-Path $root "backend\.venv"))) {
    Write-Host "backend: uv sync"
    Push-Location (Join-Path $root "backend"); uv sync; Pop-Location
}
if (-not (Test-Path (Join-Path $root "frontend\node_modules"))) {
    Write-Host "frontend: npm install"
    Push-Location (Join-Path $root "frontend"); npm install; Pop-Location
}

$backend = "Set-Location -LiteralPath '$root\backend'; uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app"
$frontend = "Set-Location -LiteralPath '$root\frontend'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backend
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontend

Write-Host "Backend:  http://localhost:8000/health   (docs: http://localhost:8000/docs)"
Write-Host "Frontend: http://localhost:5173"
