# Launch Riva-AGI Central Backend Server in PowerShell
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

# Ensure .venv python is used
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "[!] Virtual environment not found at .venv. Creating..." -ForegroundColor Yellow
    python -m venv .venv
    & $venvPython -m pip install -r requirements.txt
}

Write-Host "===============================================================" -ForegroundColor Cyan
Write-Host "  Riva-AGI Central Backend Server" -ForegroundColor Green
Write-Host "  Starting on http://localhost:8000" -ForegroundColor Green
Write-Host "  Interactive API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "===============================================================" -ForegroundColor Cyan

& $venvPython -m Backend.main
