@echo off
REM Build Windows .exe (run on Windows only)
REM Needs: pip install pyinstaller cryptography
cd /d "%~dp0"

echo ========================================
echo   Building Klyuchnica (Keeper)
echo ========================================

python -m pip install -r requirements.txt
python -m pip install pyinstaller

REM --onedir (folder mode) = fewer antivirus false positives
pyinstaller --noconfirm --clean --name "Keeper" --onedir --windowed keeper.py

echo.
echo Done. See folder dist\Keeper\
pause
