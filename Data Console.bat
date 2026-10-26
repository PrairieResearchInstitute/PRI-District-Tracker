@echo off
REM Opens the PRI District Tracker Data Console on this computer.
REM Double-click it from wherever the app folder sits: %~dp0 is this file's own
REM folder, so no drive letter is written down anywhere (estate rule).

setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo   The Python launcher py was not found. Install Python 3.13 from python.org.
    echo.
    pause
    exit /b 1
)

if not exist "config.local.json" (
    echo   config.local.json is missing. Running SETUP.bat first.
    echo.
    call "%~dp0SETUP.bat"
)

echo.
echo   PRI District Tracker: Data Console
echo   ----------------------------------
echo   Back-office. Runs on this computer only. Not the public website.
echo   The browser opens by itself. Close this window to stop the console.
echo.
py scripts\admin_server.py
if errorlevel 1 (
    echo.
    echo   The console stopped with an error. The lines above say why.
    echo.
    pause
)
endlocal
