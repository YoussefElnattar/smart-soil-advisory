@echo off
REM Smart Soil Advisory Platform - double-click to start.
REM First run: creates .venv and installs requirements (needs internet, about 1 minute).
REM Then it starts the web app and opens http://127.0.0.1:8000 in your browser.
REM Keep this window open while you use the app; close it to stop the app.
title Smart Soil Advisory Platform
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 run.py %*
    goto end
)
where python >nul 2>nul
if %errorlevel%==0 (
    python run.py %*
    goto end
)
echo.
echo   Python 3 was not found. Install it from https://www.python.org/downloads/
echo   (tick "Add python.exe to PATH" during setup), then double-click run.bat again.
echo.

:end
if errorlevel 1 (
    echo.
    echo   The app stopped with an error - see the messages above.
    pause
)
