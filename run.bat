@echo off
REM Launch Riva-AGI Central Backend Server on Windows Command Prompt
cd /d "%~dp0"

set VENV_PYTHON=.venv\Scripts\python.exe

if not exist "%VENV_PYTHON%" (
    echo [!] Virtual environment not found. Creating .venv...
    python -m venv .venv
    %VENV_PYTHON% -m pip install -r requirements.txt
)

echo ===============================================================
echo   Riva-AGI Central Backend Server
echo   Starting on http://localhost:8000
echo   Interactive API Docs: http://localhost:8000/docs
echo ===============================================================

"%VENV_PYTHON%" -m Backend.main
pause
