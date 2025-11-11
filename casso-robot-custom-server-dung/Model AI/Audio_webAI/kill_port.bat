@echo off
chcp 65001 >nul

set PORT=8765

echo Checking for processes using port %PORT%...

REM Tìm process đang dùng port
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
    echo Found process using port %PORT%: PID %%a
    echo Killing process %%a...
    taskkill /F /PID %%a >nul 2>&1
    if errorlevel 1 (
        echo [WARNING] Could not kill process %%a
    ) else (
        echo [OK] Process %%a killed successfully
    )
)

echo Port %PORT% is now free!
timeout /t 1 >nul
