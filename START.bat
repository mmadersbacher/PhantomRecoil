@echo off
setlocal EnableExtensions
echo ==============================================
echo  Starting Phantom Recoil...
echo ==============================================
echo [System] Checking requirements...
where python >nul 2>&1
if errorlevel 1 (
	echo [ERROR] Python is not installed or not in PATH.
	exit /b 1
)

python -m pip install pywebview pywin32 pillow >nul 2>&1
if errorlevel 1 (
	echo [ERROR] Failed to install required Python packages.
	exit /b 1
)

if not exist "ui_app.py" (
	echo [ERROR] ui_app.py not found in current directory.
	exit /b 1
)

echo [System] Launching App...
python ui_app.py
pause
