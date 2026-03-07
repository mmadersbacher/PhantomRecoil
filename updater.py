import urllib.request
import urllib.error
import json
import sys
import webbrowser
import ctypes
import logging
import re

# Semantic version of the CURRENT build
__version__ = "v1.0.6"

GITHUB_REPO = "mmadersbacher/RainbowSixRecoil"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
REQUEST_TIMEOUT_SECONDS = 5


logger = logging.getLogger(__name__)


def _parse_version(version_text):
    """Parse tags like v1.2.3 or 1.2.3 into a comparable tuple."""
    if not version_text:
        return None
    match = re.match(r'^v?(\d+)\.(\d+)\.(\d+)$', str(version_text).strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def _is_newer_version(current, latest):
    current_parsed = _parse_version(current)
    latest_parsed = _parse_version(latest)
    if current_parsed is None or latest_parsed is None:
        return False
    return latest_parsed > current_parsed

def check_for_updates():
    """
    Checks the GitHub repository for new releases.
    Returns the release URL and the new version if an update is available, else (None, None).
    """
    try:
        req = urllib.request.Request(API_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            remaining = response.headers.get('X-RateLimit-Remaining')
            if remaining is not None:
                logger.info("[Updater] GitHub rate limit remaining: %s", remaining)

            payload = response.read().decode('utf-8')
            data = json.loads(payload)
            latest_version = data.get("tag_name", "")
            if _parse_version(latest_version) is None:
                logger.warning("[Updater] Ignoring release with invalid version tag: %s", latest_version)
                return None, None
            
            if latest_version and _is_newer_version(__version__, latest_version):
                logger.info("[Updater] New version found: %s (Current: %s)", latest_version, __version__)
                
                release_url = data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/latest")
                return release_url, latest_version
            logger.info("[Updater] No newer release available.")

    except urllib.error.HTTPError as e:
        if e.code == 403:
            logger.warning("[Updater] Rate limited by GitHub API (HTTP 403).")
        else:
            logger.warning("[Updater] HTTP error during update check: %s", e)
    except urllib.error.URLError as e:
        logger.warning("[Updater] Network error during update check: %s", e)
    except TimeoutError:
        logger.warning("[Updater] Timeout while checking for updates.")
    except json.JSONDecodeError as e:
        logger.warning("[Updater] Invalid JSON from GitHub API: %s", e)
    except Exception as e:
        logger.exception("[Updater] Unexpected failure during update check: %s", e)
        
    return None, None

def notify_update(release_url, version):
    """
    Prompts the user about the new update and opens the browser if they accept.
    This replaces the old batch-script silent auto-update to prevent Antivirus flagging.
    """
    try:
        logger.info("[Updater] Prompting user for update to %s...", version)
        
        # If running from source (python ui_app.py), sys.executable is python.exe. 
        # We only want to auto-update if we are the bundled .exe.
        if not getattr(sys, 'frozen', False):
            logger.info("[Updater] Running from source, skipping update notification.")
            return

        MB_YESNO = 0x04
        MB_ICONINFORMATION = 0x40
        MB_TOPMOST = 0x40000
        IDYES = 6
        
        text = (
            f"A new version ({version}) of Phantom Recoil is available!\n\n"
            "The download page will open in your browser.\n"
            "Only download releases from the official GitHub repository."
        )
        title = "Update Available"
        
        result = ctypes.windll.user32.MessageBoxW(0, text, title, MB_YESNO | MB_ICONINFORMATION | MB_TOPMOST)
        
        if result == IDYES:
            webbrowser.open(release_url)
            
    except Exception as e:
        logger.exception("[Updater] Update notification failed: %s", e)

def run_auto_updater():
    """Main entrypoint for the updater routine."""
    logger.info("[Updater] Checking for updates (Current: %s)...", __version__)
    release_url, version = check_for_updates()
    if release_url:
        notify_update(release_url, version)
