@echo off
REM PRI District Tracker setup. Checks Python, creates config.local.json from
REM config.template.json, and on the drive points dataFolder at ..\..\data\pri-district-tracker.
REM Nothing to install: the generator uses the Python standard library only.

setlocal
cd /d "%~dp0"

echo.
echo PRI District Tracker setup
echo --------------------------
echo.

where py >nul 2>nul
if errorlevel 1 (
    echo   The Python launcher py was not found. Install Python 3.13 from python.org and run SETUP.bat again.
    echo.
    pause
    exit /b 1
)
for /f "delims=" %%v in ('py --version') do echo   %%v found.

py scripts\app_config.py --init
if errorlevel 1 goto failed

if exist "..\..\data\pri-district-tracker\" (
    py scripts\app_config.py --set-data-folder ..\..\data\pri-district-tracker
    if errorlevel 1 goto failed
) else (
    echo   No ..\..\data\pri-district-tracker folder here, so backups stay beside the app.
)

REM The hosted PHP layer's checks (py tools\check.py) need a PHP with pdo_pgsql.
REM scripts\find_php.py looks at PRI_PHP, tools\php and the PATH. On the drive the
REM portable PHP that PaCELab Equip carries is copied in once (git-ignored).
if not exist "tools\php\php.exe" (
    if exist "..\pacelab-equip\tools\php\php.exe" (
        echo   Copying the portable PHP from ..\pacelab-equip\tools\php into tools\php ...
        robocopy "..\pacelab-equip\tools\php" "tools\php" /E /NFL /NDL /NJH /NJS /NP >nul
        if errorlevel 8 goto failed
    ) else (
        echo   No PHP in tools\php. Set PRI_PHP to a php.exe with pdo_pgsql, or the gate's PHP checks fail.
    )
)
py scripts\find_php.py

if not exist "assets\vendor\toolkit.local.js" (
    echo   assets\vendor is missing. Run py scripts\make_vendor.py once while online before building.
)

echo.
py scripts\app_config.py --show
echo.
echo Setup complete. Build the site with: py scripts\build_site.py
echo.
pause
endlocal
exit /b 0

:failed
echo.
echo   Setup stopped. The messages above say why.
echo.
pause
exit /b 1
