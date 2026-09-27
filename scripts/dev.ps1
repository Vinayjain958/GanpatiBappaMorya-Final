# Starts the LocaLens frontend and backend dev servers together.
# Usage: powershell -File scripts/dev.ps1

$root = Split-Path -Parent $PSScriptRoot

$api = Start-Process -PassThru -NoNewWindow powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root/apps/api'; .venv\Scripts\Activate.ps1; uvicorn src.main:app --reload --port 8000"
)

$web = Start-Process -PassThru -NoNewWindow powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root/apps/web'; npm run dev"
)

Write-Host "API:  http://localhost:8000/api/v1/health"
Write-Host "Web:  http://localhost:3000"
Write-Host "Press Ctrl+C to stop watching (processes keep running in their own windows)."

Wait-Process -Id $api.Id, $web.Id
