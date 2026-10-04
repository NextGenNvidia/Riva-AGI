@echo off
REM Launch RIVA Web Application & Gateway Server on Windows (CMD)

cd /d "%~dp0\.."
set "PROJECT_ROOT=%CD%"

REM Initialize virtual environment if missing
if not exist ".venv" (
    echo Creating Python virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Sync dependencies
pip install -q -r voice_speech\requirements.txt

REM Add project root to PYTHONPATH
set "PYTHONPATH=%PROJECT_ROOT%;%PYTHONPATH%"

echo ===============================================================
echo   RIVA — Real-Time Voice Interface (Voice/Speech Engine)
echo   Server running on http://localhost:8000
echo ===============================================================

python -m voice_speech.web_server
