@echo off
cd /d "%~dp0"
echo Launching OmniHub... Close this window to close the app.

if exist "venv\Scripts\python.exe" (
    echo Using existing virtual environment: venv.
    call "venv\Scripts\activate.bat"
) else (
    echo No virtual environment found - creating one.
    python -m venv venv
    call "venv\Scripts\activate.bat"
    python -m pip install --upgrade pip
    pip install -r requirements.txt
)

python app.py

rem Only keep the window open if the app failed to start, so errors are visible.
if errorlevel 1 pause
