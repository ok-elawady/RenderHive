@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo RenderHive Worker Multi-DCC Build v1.4.1
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python environment...
    where py >nul 2>nul
    if errorlevel 1 (
        echo ERROR: Python launcher was not found. Please install Python 3.10+ and add it to PATH.
        goto :error
    )
    py -3 -m venv .venv
    if errorlevel 1 goto :error
)

echo Activating Python virtual environment...
call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :error

echo Upgrading pip and installing requirements...
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo Running unit tests...
set RENDERHIVE_TESTING=1
python -m unittest discover -s tests -p "test_*.py"
set RENDERHIVE_TESTING=
if errorlevel 1 goto :error

echo Building executable with PyInstaller...
python -m PyInstaller --noconfirm --clean RenderHiveWorker.spec
if errorlevel 1 goto :error

echo.
echo ============================================================
echo BUILD SUCCEEDED!
echo Output: %CD%\dist\RenderHive Worker\RenderHive Worker.exe
echo ============================================================
echo.
pause
exit /b 0

:error
echo.
echo ============================================================
echo BUILD FAILED! (Error code: %errorlevel%)
echo Check the messages above for details.
echo ============================================================
echo.
pause
exit /b 1
