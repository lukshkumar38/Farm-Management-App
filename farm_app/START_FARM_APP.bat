@echo off
title 3 Star Layer Farm - Starting...
echo.
echo  ============================================
echo    3 STAR LAYER FARM - Management System
echo  ============================================
echo.
echo  Starting server, please wait...
echo.

REM Check if Python is installed using the 'py' launcher
py --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python is not installed or configured correctly!
    echo  Please install Python from https://python.org
    echo  Make sure to check "Add Python to PATH" during install
    pause
    exit
)

REM Install Flask and openpyxl if not already installed using 'py -m pip'
py -m pip show flask >nul 2>&1
if errorlevel 1 (
    echo  Installing Flask and dependencies for first time setup...
    py -m pip install flask openpyxl
)

echo  Server running at: http://localhost:5000
echo  Opening browser...
echo.
echo  ============================================
echo   IMPORTANT: DO NOT CLOSE THIS WINDOW
echo   Closing it will stop the app completely.
echo  ============================================
echo.
echo  (To stop the server, close this window)
echo.

REM Open browser after 2 seconds
start "" /b timeout /t 2 /nobreak >nul
start "" "http://localhost:5000"

REM Start the Flask app using the correct 'py' engine
cd /d "%~dp0"
py app.py

pause