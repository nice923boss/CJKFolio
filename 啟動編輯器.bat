@echo off
REM ============================================================
REM  CJKFolio editor launcher  (Phase 2 canvas + edit engine)
REM  Real-window canvas / IME test for GAPS #19.
REM  Double-click to run; close the window to quit.
REM  Optional: drag a .doc.json file onto this .bat to open it.
REM ============================================================
cd /d "%~dp0"
title CJKFolio Editor

python -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo [!] PySide6 is not installed for the default Python.
    echo     Install it, then re-run:  python -m pip install PySide6
    echo.
    pause
    exit /b 1
)

echo Launching CJKFolio editor ...
python "editor\app.py" %*
if errorlevel 1 (
    echo.
    echo [X] Editor exited with an error ^(see the message above^).
    pause
    exit /b 1
)
