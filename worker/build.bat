@echo off
echo Building RenderHive Worker PySide Application...

echo.
echo Looking for Python...
set PYTHON_EXE=python
if exist ..\backend\.venv\Scripts\python.exe (
    set PYTHON_EXE=..\backend\.venv\Scripts\python.exe
)

echo.
echo Creating local virtual environment...
%PYTHON_EXE% -m venv .venv
call .venv\Scripts\activate.bat

echo.
echo Installing dependencies...
python -m pip install -r requirements.txt

echo.
echo Packaging with PyInstaller...
pyinstaller --noconfirm --onedir --windowed --name "RenderHiveWorker" --icon "assets\icon.ico" --add-data "assets;assets" "app.py"

echo.
echo Build complete! You can find the executable in the 'dist/RenderHiveWorker/' folder.
pause
