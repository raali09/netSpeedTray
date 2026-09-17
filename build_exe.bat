@echo off
setlocal

set "SCRIPT=src\netspeedtray.py"
set "APPNAME=NetSpeedTray"
set "ICON=assets\icon.ico"
set "PNG=assets\icon.png"

if not exist "%SCRIPT%" (
    echo ERROR: %SCRIPT% was not found. Run this file from the project root.
    pause
    exit /b 1
)

if not exist "%ICON%" (
    echo WARNING: %ICON% not found. Generating icon...
    py make_icon.py
)

py -m pip install --upgrade pyinstaller psutil
if errorlevel 1 (
    echo ERROR: Could not install build dependencies.
    pause
    exit /b 1
)

set "ICON_FLAG="
if exist "%ICON%" set "ICON_FLAG=--icon=%ICON%"

set "DATA_FLAG="
if exist "%PNG%" set "DATA_FLAG=--add-data=%PNG%;."

py -m PyInstaller --noconfirm --clean --onefile --windowed --name "%APPNAME%" %ICON_FLAG% %DATA_FLAG% "%SCRIPT%"
if errorlevel 1 (
    echo ERROR: Build failed.
    pause
    exit /b 1
)

echo.
echo Build complete: dist\%APPNAME%.exe
echo.
pause
