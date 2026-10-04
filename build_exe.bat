@echo off
REM Сборка .exe для Windows (запускать только на Windows)
REM Требуется: pip install pyinstaller cryptography

chcp 65001 >nul
echo ========================================
echo   Сборка Ключница (Keeper)
echo ========================================

pip install -r requirements.txt
pip install pyinstaller

REM Режим «папка» (--onedir) — меньше ложных срабатываний антивирусов
pyinstaller --noconfirm --clean ^
  --name "Keeper" ^
  --onedir ^
  --windowed ^
  keeper.py

echo.
echo Готово. Смотрите папку dist\Keeper\
pause
