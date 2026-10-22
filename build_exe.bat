@echo off
rem Builds a single-file dist\Deleter.exe (no Python needed to run it).
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :fail
python -m PyInstaller --noconfirm --onefile --windowed --name Deleter --collect-all customtkinter deleter.py
if errorlevel 1 goto :fail
echo.
echo Done: dist\Deleter.exe
pause
exit /b 0
:fail
echo Build failed.
pause
exit /b 1
