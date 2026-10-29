@echo off
REM ============================================================
REM  Build Smart Vision EXE on Windows 7 (Python 3.8)
REM  Run this file from the same folder as smart_vision.py
REM ============================================================

cd /d "%~dp0"

REM 1) PyInstaller 4.10 is the last version that supports Windows 7
python -m pip install pyinstaller==4.10 pyinstaller-hooks-contrib==2022.0
if errorlevel 1 goto fail

REM 2) Copy the face cascade file next to the script so it gets bundled
python -c "import cv2,shutil,os; shutil.copy(os.path.join(cv2.data.haarcascades,'haarcascade_frontalface_default.xml'),'.')"
if errorlevel 1 goto fail

REM 3) Build (onedir). Using --console so errors are visible.
REM    After everything works, change --console to --windowed.
python -m PyInstaller --noconfirm --clean --console --name SmartVision ^
  --add-data "haarcascade_frontalface_default.xml;." ^
  --hidden-import pyautogui --hidden-import pyzbar.pyzbar ^
  smart_vision.py
if errorlevel 1 goto fail

echo.
echo Build OK: dist\SmartVision\SmartVision.exe
echo Copy the whole dist\SmartVision folder to any Windows 7 PC.
pause
exit /b 0

:fail
echo.
echo Build FAILED. Check that python is in PATH and packages are installed.
pause
exit /b 1
