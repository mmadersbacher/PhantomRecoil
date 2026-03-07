import urllib.request
import json
import os
import sys
import subprocess
import time

# Semantic version of the CURRENT build
__version__ = "v1.0.0"

GITHUB_REPO = "mmadersbacher/RainbowSixRecoil"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

def check_for_updates():
    """
    Checks the GitHub repository for new releases.
    Returns the download URL for the new .exe if an update is available, else None.
    """
    try:
        req = urllib.request.Request(API_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            latest_version = data.get("tag_name", "")
            
            if latest_version and latest_version != __version__:
                print(f"[Updater] New version found: {latest_version} (Current: {__version__})")
                
                # Find the .exe asset
                for asset in data.get("assets", []):
                    if asset.get("name", "").endswith(".exe"):
                        return asset.get("browser_download_url")
                        
    except Exception as e:
        print(f"[Updater] Failed to check for updates: {e}")
        
    return None

def download_and_update(download_url):
    """
    Downloads the new .exe to a temporary location and launches a batch script
    to replace the current running executable.
    """
    try:
        print("[Updater] Downloading new release...")
        current_exe = sys.executable
        
        # If running from source (python ui_app.py), sys.executable is python.exe. 
        # We only want to auto-update if we are the bundled .exe.
        if not getattr(sys, 'frozen', False):
            print("[Updater] Running from source, skipping auto-update execution.")
            return

        temp_dir = os.environ.get("TEMP", os.path.dirname(current_exe))
        new_exe_path = os.path.join(temp_dir, "R6_Recoil_Update.exe")
        
        # Download
        req = urllib.request.Request(download_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(new_exe_path, 'wb') as out_file:
            out_file.write(response.read())

        # Create a batch script to swap the files
        bat_path = os.path.join(temp_dir, "r6_updater.bat")
        
        with open(bat_path, "w") as f:
            f.write(f'''@echo off
timeout /t 2 /nobreak > NUL
del "{current_exe}"
move /Y "{new_exe_path}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
''')
        
        # Launch the batch script detached and exit the current app
        print("[Updater] Handing off to updater batch script...")
        subprocess.Popen(bat_path, creationflags=subprocess.CREATE_NO_WINDOW)
        sys.exit(0)
        
    except Exception as e:
        print(f"[Updater] Update failed: {e}")

def run_auto_updater():
    """Main entrypoint for the updater routine."""
    print(f"[Updater] Checking for updates (Current: {__version__})...")
    download_url = check_for_updates()
    if download_url:
        download_and_update(download_url)
