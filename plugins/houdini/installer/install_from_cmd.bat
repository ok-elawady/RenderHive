@echo off
setlocal
cd /d "%~dp0\..\.."
call install_from_cmd.bat %*
exit /b %errorlevel%
