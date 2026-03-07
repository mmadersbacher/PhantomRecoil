@echo off
setlocal EnableExtensions
echo ==============================================
echo  Starting Phantom Recoil...
echo ==============================================

if not exist "Phantom_Recoil_Standalone.exe" (
    echo [!] No executable found. Running first-time compiler...
    echo.
    call BUILD.bat
    if errorlevel 1 (
        echo [ERROR] Build failed. Application was not started.
        exit /b 1
    )
)

if not exist "Phantom_Recoil_Standalone.exe" (
    echo [ERROR] Executable still missing after build.
    exit /b 1
)

echo [System] Launching App...
start "" "Phantom_Recoil_Standalone.exe"
exit
