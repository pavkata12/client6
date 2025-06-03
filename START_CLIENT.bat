@echo off
title NetCafe Pro 2.0 - Gaming Client Launcher
color 0A

echo.
echo ========================================
echo     🎮 NetCafe Pro 2.0 Gaming Client 🎮
echo ========================================
echo.

echo [INFO] Starting NetCafe Pro 2.0 Gaming Client...
echo.

echo [STEP 1] Checking Python installation...
python --version
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

echo [STEP 2] Checking client files...
if not exist "client\netcafe_client.py" (
    echo [ERROR] Client files not found!
    echo Please run this script from the NetCafe Pro 2.0 root directory.
    pause
    exit /b 1
)

echo [STEP 3] Checking dependencies...
cd client
python -c "import PySide6; import qasync; import aiohttp; import win32api" 2>nul
if %errorlevel% neq 0 (
    echo [WARNING] Some dependencies missing. Installing...
    pip install -r requirements.txt
)

echo [STEP 4] Starting Gaming Client...
echo.
echo 💡 Client Features:
echo    🔒 Full screen lock when no session
echo    ⏰ Gaming timer overlay during session
echo    📟 System tray integration
echo    🔄 Auto-reconnection to server
echo.
echo 🎮 Starting gaming experience...
python netcafe_client.py

echo.
echo 📋 Client stopped. Check logs for details.
echo.
pause 