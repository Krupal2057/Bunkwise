# BunkWise - PowerShell Launcher Script
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  Starting BunkWise Attendance Management System  " -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

# 1. Check for .env file
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Write-Host "[*] .env not found. Creating .env from .env.example..." -ForegroundColor Yellow
        Copy-Item ".env.example" ".env"
    }
}

# 2. Determine Python interpreter
$PyExe = "python"
if (Test-Path "$ScriptDir\venv\Scripts\python.exe") {
    $PyExe = "$ScriptDir\venv\Scripts\python.exe"
    Write-Host "[*] Using virtual environment Python: $PyExe" -ForegroundColor Green
} elseif (Test-Path "$ScriptDir\.venv\Scripts\python.exe") {
    $PyExe = "$ScriptDir\.venv\Scripts\python.exe"
    Write-Host "[*] Using virtual environment Python: $PyExe" -ForegroundColor Green
} else {
    Write-Host "[!] Virtual environment not found. Creating venv..." -ForegroundColor Yellow
    python -m venv venv
    $PyExe = "$ScriptDir\venv\Scripts\python.exe"
    Write-Host "[*] Installing requirements..." -ForegroundColor Yellow
    & "$ScriptDir\venv\Scripts\pip.exe" install -r requirements.txt
}

# 3. Apply migrations
Write-Host "[*] Checking database migrations..." -ForegroundColor Cyan
& $PyExe manage.py migrate --noinput

# 4. Open browser in background
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://127.0.0.1:8000/"
} | Out-Null

# 5. Start dev server
Write-Host "`n===================================================" -ForegroundColor Green
Write-Host "  Server running at: http://127.0.0.1:8000/        " -ForegroundColor Green
Write-Host "  Press Ctrl+C to stop the server.               " -ForegroundColor Green
Write-Host "===================================================`n" -ForegroundColor Green

& $PyExe manage.py runserver 127.0.0.1:8000
