@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 installer\check.py
) else (
    python installer\check.py
)
pause
