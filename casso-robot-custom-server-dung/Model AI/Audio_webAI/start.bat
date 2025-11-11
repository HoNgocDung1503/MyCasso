@echo off
chcp 65001 >nul
echo ====================================
echo   Starting AI Chat Server
echo ====================================
echo.

cd /d "%~dp0"

REM Kiểm tra file .env tồn tại
if not exist ".env" (
    echo [ERROR] File .env không tồn tại!
    echo Vui lòng tạo file .env và thêm OPENAI_API_KEY
    echo.
    pause
    exit /b 1
)

REM Đọc API key từ .env
for /f "tokens=1,2 delims==" %%a in (.env) do (
    if "%%a"=="OPENAI_API_KEY" (
        set OPENAI_API_KEY=%%b
    )
)

REM Kiểm tra API key
if "%OPENAI_API_KEY%"=="sk-your-api-key-here" (
    echo [WARNING] API key chưa được cấu hình!
    echo Vui lòng mở file .env và thay đổi OPENAI_API_KEY
    echo.
    pause
    exit /b 1
)

if "%OPENAI_API_KEY%"=="" (
    echo [ERROR] Không tìm thấy OPENAI_API_KEY trong file .env
    echo.
    pause
    exit /b 1
)

echo [OK] API Key loaded from .env
echo.
echo ====================================
echo   Checking Port 8765
echo ====================================
echo.
echo Checking if port 8765 is already in use...

REM Kill any process using port 8765
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8765" ^| findstr "LISTENING"') do (
    echo Found process using port 8765: PID %%a
    echo Killing process %%a...
    taskkill /F /PID %%a >nul 2>&1
    if errorlevel 1 (
        echo [WARNING] Could not kill process %%a - May need admin rights
    ) else (
        echo [OK] Process %%a killed successfully
    )
)

echo [OK] Port 8765 is ready!
timeout /t 1 >nul
echo.
echo ====================================
echo   Testing Products Database
echo ====================================
echo.
echo Running products.py test...
python products.py
echo.
if errorlevel 1 (
    echo [ERROR] Products test failed!
    echo.
    pause
    exit /b 1
)
echo [OK] Products database working!
echo.
echo ====================================
echo   Starting WebSocket Server
echo ====================================
echo.
echo Starting WebSocket Server...
echo Server will run at: ws://localhost:8765
echo.
echo Press Ctrl+C to stop server
echo ====================================
echo.

REM Chạy server với API key từ .env
python server.py

pause
