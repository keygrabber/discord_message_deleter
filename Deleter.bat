@echo off
rem Double-click to open Deleter without a terminal window.
cd /d "%~dp0"
where pythonw >nul 2>&1
if errorlevel 1 (
    echo Python is not installed. Get it from https://www.python.org/downloads/ ^(tick "Add Python to PATH"^).
    pause
    exit /b 1
)
python -c "import requests, customtkinter" >nul 2>&1
if errorlevel 1 (
    echo First start: installing required packages...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        pause
        exit /b 1
    )
)
start "" pythonw deleter.py
