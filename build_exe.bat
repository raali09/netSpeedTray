@echo off
setlocal enabledelayedexpansion

rem ==========================================================================
rem  NetSpeedTray - Windows build script
rem  Builds a single-file windowed NetSpeedTray.exe using PyInstaller.
rem  Run this file from the project root directory.
rem ==========================================================================

set "SCRIPT=src\netspeedtray.py"
set "APPNAME=NetSpeedTray"
set "ICON=assets\icon.ico"
set "PNG=assets\icon.png"
set "VERSION_FILE=VERSION"
set "SPEC_FILE=netspeedtray.spec"
set "VERSION=2.7.0"

if not exist "%SCRIPT%" (
    echo ERROR: %SCRIPT% was not found. Run this file from the project root.
    pause
    exit /b 1
)

rem --- Read version from VERSION file (single line, robust to CRLF) ---------
set "VERSION=2.7.0"
if exist "%VERSION_FILE%" (
    for /f "usebackq delims=" %%a in ("%VERSION_FILE%") do set "VERSION=%%a"
)
if "!VERSION!"=="" set "VERSION=2.7.0"

echo Building %APPNAME% v%VERSION%
echo.

rem --- Generate the app icon if it is missing -------------------------------
if not exist "%ICON%" (
    echo WARNING: %ICON% not found. Generating icon...
    py make_icon.py
    if errorlevel 1 (
        echo ERROR: Icon generation failed.
        pause
        exit /b 1
    )
)

rem --- Install build / runtime dependencies ---------------------------------
echo Installing dependencies...
py -m pip install --upgrade pip
py -m pip install --upgrade pyinstaller psutil pillow
if errorlevel 1 (
    echo ERROR: Could not install build dependencies.
    pause
    exit /b 1
)

rem --- Build via the .spec file (preferred), fall back to CLI form ----------
set "ICON_FLAG="
if exist "%ICON%" set "ICON_FLAG=--icon=%ICON%"

set "DATA_FLAG="
if exist "%PNG%" set "DATA_FLAG=--add-data=%PNG%;."

if exist "%SPEC_FILE%" (
    echo Using spec file: %SPEC_FILE%
    py -m PyInstaller --noconfirm --clean "%SPEC_FILE%"
) else (
    echo Spec file not found, falling back to command-line build.
    py -m PyInstaller --noconfirm --clean --onefile --windowed ^
        --name "%APPNAME%" ^
        --version-file=version_info.txt ^
        %ICON_FLAG% %DATA_FLAG% ^
        "%SCRIPT%"
)

if errorlevel 1 (
    echo ERROR: Build failed.
    pause
    exit /b 1
)

if not exist "dist\%APPNAME%.exe" (
    echo ERROR: dist\%APPNAME%.exe was not produced.
    pause
    exit /b 1
)

echo.
echo Build complete: dist\%APPNAME%.exe  ^(v%VERSION%^)
echo.
pause
