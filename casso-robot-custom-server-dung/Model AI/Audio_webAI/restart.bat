@echo off
chcp 65001 >nul

echo ====================================
echo   RESTART SERVER
echo ====================================
echo.

cd /d "%~dp0"

echo Killing old server process on port 8765...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8765" ^| findstr "LISTENING"') do (
    echo Killing PID %%a...
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo [OK] Old server stopped!
echo.
echo Starting new server...
timeout /t 2 >nul

call start.bat
