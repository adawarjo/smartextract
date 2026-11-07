@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller==6.22.3
if errorlevel 1 goto gagal
python -m PyInstaller --noconfirm --clean SmartExtract.spec
if errorlevel 1 goto gagal
echo.
echo Selesai: dist\SmartExtract.exe
pause
exit /b 0

:gagal
echo.
echo Pembuatan exe gagal.
pause
exit /b 1
