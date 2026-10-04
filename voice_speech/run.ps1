# Launch RIVA Web Application & Gateway Server on Windows PowerShell
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
Set-Location $projectRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment..."
    python -m venv .venv
}

# Activate virtual environment
if (Test-Path ".venv\Scripts\Activate.ps1") {
    & .venv\Scripts\Activate.ps1
}

pip install -q -r voice_speech\requirements.txt

$env:PYTHONPATH = "$projectRoot;$env:PYTHONPATH"

Write-Host "==============================================================="
Write-Host "  RIVA — Real-Time Voice Interface (Voice/Speech Engine)"
Write-Host "  Server running on http://localhost:8000"
Write-Host "==============================================================="

python -m voice_speech.web_server
