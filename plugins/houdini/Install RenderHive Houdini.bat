@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo  RenderHive Houdini v2.0.5 - Known-Good Shelf Installer
echo ============================================================
echo.
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 installer\install.py
) else (
    python installer\install.py
)
if errorlevel 1 (
    echo.
    echo Installation FAILED.
    pause
    exit /b 1
)
echo.
echo Installation completed. Close this window and start Houdini.
echo Open RenderHive from the RenderHive shelf or RenderHive menu.
pause
