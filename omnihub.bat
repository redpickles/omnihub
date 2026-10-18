@echo off
cd /d "%~dp0"
echo Launching OmniHub... Close this window to close the app.
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" app.py
) else (
    python app.py
)
rem Only keep the window open if the app failed to start, so errors are visible.
if errorlevel 1 pause
