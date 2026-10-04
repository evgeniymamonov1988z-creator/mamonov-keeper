@echo off
REM Klyuchnica - launcher. Double-click to run.
cd /d "%~dp0"

set "PY="
where pythonw >nul 2>&1 && set "PY=pythonw"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY goto no_python

python -c "import cryptography, uiautomation" >nul 2>&1
if errorlevel 1 (
    echo First run: installing required components...
    python -m pip install -r requirements.txt
)

start "" %PY% "%~dp0keeper.py"
goto :eof

:no_python
echo [ERROR] Python not found.
echo Install Python from https://www.python.org/downloads/
echo and tick "Add Python to PATH" during setup.
pause
