@echo off
title BunkWise - Starting Development Server
setlocal enabledelayedexpansion

:: Navigate to the directory where this script is located
cd /d "%~dp0"

echo ===================================================
echo   Starting BunkWise Attendance Management System
echo ===================================================
echo.

:: 1. Check for .env file, copy from .env.example if missing
if not exist ".env" (
    if exist ".env.example" (
        echo [*] .env not found. Creating .env from .env.example...
        copy .env.example .env >nul
    )
)

:: 2. Check and activate virtual environment
set "PY_EXE=python"
if exist "venv\Scripts\python.exe" (
    set "PY_EXE=%~dp0venv\Scripts\python.exe"
    echo [*] Using virtual environment Python: !PY_EXE!
) else if exist ".venv\Scripts\python.exe" (
    set "PY_EXE=%~dp0.venv\Scripts\python.exe"
    echo [*] Using virtual environment Python: !PY_EXE!
) else (
    echo [!] Virtual environment not found.
    echo [*] Creating virtual environment (venv)...
    python -m venv venv
    if errorlevel 1 (
        echo [X] Failed to create virtual environment. Make sure Python is installed and added to PATH.
        pause
        exit /b 1
    )
    set "PY_EXE=%~dp0venv\Scripts\python.exe"
    echo [*] Installing requirements...
    "%~dp0venv\Scripts\pip.exe" install -r requirements.txt
)

:: 3. Run database migrations
echo [*] Checking database migrations...
"!PY_EXE!" manage.py migrate --noinput
if errorlevel 1 (
    echo [!] Database migration encountered an issue. Check settings or database configuration.
)

:: 4. Launch browser after a brief delay in the background
echo [*] Opening http://127.0.0.1:8000/ in your browser...
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8000/"

:: 5. Start the Django development server
echo.
echo ===================================================
echo   Server running at: http://127.0.0.1:8000/
echo   Press Ctrl+C to stop the server.
echo ===================================================
echo.

"!PY_EXE!" manage.py runserver 127.0.0.1:8000

if errorlevel 1 (
    echo.
    echo [X] Server stopped with an error.
    pause
)
