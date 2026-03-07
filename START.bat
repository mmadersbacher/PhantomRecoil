@echo off
echo Installing required packages...
pip install pywebview pywin32

echo Starting R6 Recoil Controller (Web GUI)...
python ui_app.py
pause
