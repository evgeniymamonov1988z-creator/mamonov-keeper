@echo off
REM Klyuchnica - DIAGNOSTIC. This window stays open and shows errors.
cd /d "%~dp0"
echo ====================================================
echo   KLYUCHNICA - startup check
echo ====================================================
echo.

echo [1] Checking Python...
python --version
if errorlevel 1 (
    echo.
    echo [X] Python NOT found or not in PATH.
    echo     Download: https://www.python.org/downloads/
    echo     Tick "Add Python to PATH" during setup.
    echo.
    pause
    exit /b 1
)
echo.

echo [2] Checking encryption library...
python -c "import cryptography; print('cryptography OK', cryptography.__version__)"
if errorlevel 1 (
    echo     Not found - installing...
    python -m pip install -r requirements.txt
)
echo.

echo [3] Starting program (console stays open)...
echo ----------------------------------------------------
python "%~dp0keeper.py"
echo ----------------------------------------------------
echo.
echo [DONE] If you see a red error above, send it to me (screenshot).
echo.
pause
