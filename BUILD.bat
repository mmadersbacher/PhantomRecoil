@echo off
setlocal EnableExtensions
echo ==============================================
echo  Phantom Recoil - Build Orchestrator
echo ==============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    exit /b 1
)

if not exist "icon.ico" (
    echo [ERROR] Required file missing: icon.ico
    exit /b 1
)

if not exist "web\index.html" (
    echo [ERROR] Required file missing: web\index.html
    exit /b 1
)

if not exist "ui_app.py" (
    echo [ERROR] Required file missing: ui_app.py
    exit /b 1
)

:: Check for PyInstaller
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo [System] Installing PyInstaller compiler...
    python -m pip install pyinstaller >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Failed to install PyInstaller.
        exit /b 1
    )
)

echo [System] Cleaning old build remnants...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist Phantom_Recoil.exe del /q Phantom_Recoil.exe
if exist Phantom_Recoil_Standalone.exe del /q Phantom_Recoil_Standalone.exe

echo [System] Compiling Phantom_Recoil.exe with Pyinstaller...
pyinstaller --noconfirm --onedir --windowed --noconsole --name "Phantom_Recoil" --icon="icon.ico" --add-data "web;web" --add-data "icon.ico;." "ui_app.py"
if errorlevel 1 (
    echo [ERROR] Onedir build failed.
    exit /b 1
)

:: Move the EXE up and clean the ugly PyInstaller folders
echo [System] Packaging application...
move dist\Phantom_Recoil\Phantom_Recoil.exe .\ >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to move Phantom_Recoil.exe.
    exit /b 1
)

if not exist "_internal" mkdir _internal
copy dist\Phantom_Recoil\_internal\*.* _internal\ >nul 2>&1

:: Create a standalone ONE-FILE compile
pyinstaller --noconfirm --onefile --windowed --noconsole --name "Phantom_Recoil_Standalone" --icon="icon.ico" --add-data "web;web" --add-data "icon.ico;." "ui_app.py"
if errorlevel 1 (
    echo [ERROR] Standalone build failed.
    exit /b 1
)

echo.
echo [System] Cleaning up build folders...
move /Y dist\Phantom_Recoil_Standalone.exe .\ >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to move Phantom_Recoil_Standalone.exe.
    exit /b 1
)

if not exist "Phantom_Recoil_Standalone.exe" (
    echo [ERROR] Build output missing: Phantom_Recoil_Standalone.exe
    exit /b 1
)

for %%I in (Phantom_Recoil_Standalone.exe) do set EXE_SIZE=%%~zI
if "%EXE_SIZE%"=="" (
    echo [ERROR] Unable to validate output file size.
    exit /b 1
)
if %EXE_SIZE% LSS 500000 (
    echo [ERROR] Output file seems too small and may be corrupted.
    exit /b 1
)

where certutil >nul 2>&1
if errorlevel 1 (
    echo [WARN] certutil not found. Skipping checksum generation.
) else (
    echo [System] Generating SHA256 checksum...
    certutil -hashfile "Phantom_Recoil_Standalone.exe" SHA256 > SHA256SUMS.txt
    if errorlevel 1 (
        echo [WARN] Failed to generate SHA256SUMS.txt.
    ) else (
        echo [System] Wrote checksum file: SHA256SUMS.txt
    )
)

rmdir /s /q build
rmdir /s /q dist

echo.
echo ==============================================
echo  SUCCESS!
echo  Your executable is ready: Phantom_Recoil_Standalone.exe
echo ==============================================
pause
endlocal
