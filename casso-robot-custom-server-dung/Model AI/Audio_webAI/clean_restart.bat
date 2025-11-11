@echo off
chcp 65001 >nul

echo ====================================
echo   CLEAN RESTART SERVER
echo ====================================
echo.

cd /d "%~dp0"

REM Xóa Python cache
echo Cleaning Python cache...
if exist __pycache__ (
    rd /s /q __pycache__
    echo [OK] Deleted __pycache__
)

if exist products.pyc (
    del /f products.pyc
    echo [OK] Deleted products.pyc
)

echo.
echo Killing old server on port 8765...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8765" ^| findstr "LISTENING"') do (
    echo Killing PID %%a...
    taskkill /F /PID %%a >nul 2>&1
)

timeout /t 2 >nul
echo.
echo [OK] Ready to start with fresh code!
echo.

REM Chạy start.bat
call start.bat
