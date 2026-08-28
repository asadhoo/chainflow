@echo off
echo ============================================
echo   ChainFlow - Supply Chain Dashboard
echo   Installation Script
echo ============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed!
    echo.
    echo Please download Python from: https://www.python.org/downloads/
    echo IMPORTANT: Check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

echo Python found. Installing required packages...
echo.

pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Some packages failed to install.
    echo Try running: pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Installation Complete!
echo   Run RUN.bat to start the application.
echo ============================================
echo.
pause
