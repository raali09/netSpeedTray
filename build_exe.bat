@echo off
setlocal

set "SCRIPT=src\netspeedtray.py"
set "APPNAME=NetSpeedTray"

if not exist "%SCRIPT%" (
    echo ERROR: %SCRIPT% was not found. Run this file from the project root.
    pause
    exit /b 1
)

py -m pip install --upgrade pyinstaller psutil
if errorlevel 1 (
    echo ERROR: Could not install build dependencies.
    pause
    exit /b 1
)

py -m PyInstaller --noconfirm --clean --onefile --windowed --name "%APPNAME%" "%SCRIPT%"
if errorlevel 1 (
    echo ERROR: Build failed.
    pause
    exit /b 1
)

echo.
echo Build complete: dist\%APPNAME%.exe
echo.
pause
