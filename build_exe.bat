@echo off
REM ============================================================
REM  Build Smart Vision EXE on Windows 7 (Python 3.8)
REM  Run this file from the same folder as smart_vision.py
REM ============================================================

cd /d "%~dp0"

REM 1) PyInstaller 4.10 is the last version that supports Windows 7
python -m pip install pyinstaller==4.10 pyinstaller-hooks-contrib==2022.0
if errorlevel 1 goto fail

REM 2) Copy the cascade files next to the script so they get bundled
python -c "import cv2,shutil,os,glob; src=cv2.data.haarcascades; names=['haarcascade_frontalface_default.xml','haarcascade_frontalface_alt2.xml','haarcascade_fullbody.xml','haarcascade_upperbody.xml']; [shutil.copy(os.path.join(src,n),'.') for n in names if os.path.isfile(os.path.join(src,n))]"
if errorlevel 1 goto fail

REM 3) Build (onedir). Using --console so errors are visible.
REM    After everything works, change --console to --windowed.
python -m PyInstaller --noconfirm --clean --console --name SmartVision ^
  --add-data "haarcascade_frontalface_default.xml;." ^
  --add-data "haarcascade_frontalface_alt2.xml;." ^
  --hidden-import svcore.app --hidden-import svcore.vision ^
  --hidden-import svcore.panels --hidden-import svcore.camera ^
  --hidden-import svcore.faceid --hidden-import svcore.counter ^
  --hidden-import svcore.qr_engine --hidden-import svcore.hand ^
  --hidden-import svcore.telegram --hidden-import svcore.autolock ^
  --hidden-import svcore.scanner --hidden-import svcore.photobooth ^
  --hidden-import svcore.pdfwriter --hidden-import svcore.stats ^
  --hidden-import svcore.voice --hidden-import svcore.textdraw ^
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
