@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo RenderHive Worker Multi-DCC Build v1.4.1
echo ============================================================

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python environment...
    where py >nul 2>nul
    if errorlevel 1 (
        echo ERROR: Python launcher was not found.
        exit /b 1
    )
    py -3 -m venv .venv
    if errorlevel 1 exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

set RENDERHIVE_TESTING=1
python -m unittest discover -s tests -p "test_*.py"
set RENDERHIVE_TESTING=
if errorlevel 1 exit /b 1

python -m PyInstaller --noconfirm --clean RenderHiveWorker.spec
if errorlevel 1 exit /b 1

echo.
echo Build completed:
echo %CD%\dist\RenderHive Worker\RenderHive Worker.exe
exit /b 0
