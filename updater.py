import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

# Semantic version of the CURRENT build
__version__ = "v1.0.23"

GITHUB_REPO = "mmadersbacher/PhantomRecoil"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"
LATEST_MANIFEST_URL = f"{RELEASES_URL}/latest/download/latest.json"
REQUEST_TIMEOUT_SECONDS = 8
DOWNLOAD_TIMEOUT_SECONDS = 120
UPDATER_USER_AGENT = "PhantomRecoil-Updater/1.0"


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


def _normalize_version_tag(version_text):
    parsed = _parse_version(version_text)
    if parsed is None:
        return None
    return f"v{parsed[0]}.{parsed[1]}.{parsed[2]}"


def _normalize_sha256(value):
    text = str(value or "").strip().lower()
    if re.fullmatch(r"[a-f0-9]{64}", text) is None:
        return None
    return text


def _normalize_manifest_asset(asset_data):
    if not isinstance(asset_data, dict):
        return None
    name = str(asset_data.get("name", "")).strip()
    url = str(asset_data.get("url") or asset_data.get("browser_download_url") or "").strip()
    if not name or not url:
        return None
    if not re.match(r"^https://", url, flags=re.IGNORECASE):
        return None

    normalized = {
        "name": name,
        "url": url,
    }
    sha256 = _normalize_sha256(asset_data.get("sha256"))
    if sha256:
        normalized["sha256"] = sha256
    return normalized


def _parse_latest_manifest(payload):
    if not isinstance(payload, dict):
        return None

    version = _normalize_version_tag(payload.get("version") or payload.get("tag_name"))
    if version is None:
        return None

    assets_raw = payload.get("assets")
    if not isinstance(assets_raw, dict):
        return None

    portable_asset = _normalize_manifest_asset(assets_raw.get("portable"))
    installer_asset = _normalize_manifest_asset(assets_raw.get("installer"))
    checksums_asset = _normalize_manifest_asset(assets_raw.get("checksums"))

    if portable_asset is None and installer_asset is None:
        return None

    release_url = str(payload.get("release_url") or f"{RELEASES_URL}/tag/{version}").strip()
    if not re.match(r"^https://", release_url, flags=re.IGNORECASE):
        release_url = f"{RELEASES_URL}/tag/{version}"

    normalized = {
        "version": version,
        "release_url": release_url,
        "assets": {
            "portable": portable_asset,
            "installer": installer_asset,
            "checksums": checksums_asset,
        },
    }
    return normalized


def _read_json(url, timeout):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UPDATER_USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is not None:
            logger.info("[Updater] GitHub rate limit remaining: %s", remaining)
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _get_latest_release():
    try:
        data = _read_json(API_URL, REQUEST_TIMEOUT_SECONDS)
        if not isinstance(data, dict):
            logger.warning("[Updater] Unexpected release payload type: %s", type(data).__name__)
            return None
        return data
    except urllib.error.HTTPError as err:
        if err.code == 403:
            logger.warning("[Updater] Rate limited by GitHub API (HTTP 403).")
        else:
            logger.warning("[Updater] HTTP error during update check: %s", err)
    except urllib.error.URLError as err:
        logger.warning("[Updater] Network error during update check: %s", err)
    except TimeoutError:
        logger.warning("[Updater] Timeout while checking for updates.")
    except json.JSONDecodeError as err:
        logger.warning("[Updater] Invalid JSON from GitHub API: %s", err)
    except Exception as err:
        logger.exception("[Updater] Unexpected failure during update check: %s", err)
    return None


def _get_latest_manifest():
    try:
        raw = _read_json(LATEST_MANIFEST_URL, REQUEST_TIMEOUT_SECONDS)
        parsed = _parse_latest_manifest(raw)
        if parsed is None:
            logger.warning("[Updater] latest.json is present but invalid. Falling back to GitHub API.")
            return None
        return parsed
    except urllib.error.HTTPError as err:
        if err.code not in (404,):
            logger.warning("[Updater] HTTP error while fetching latest.json: %s", err)
    except urllib.error.URLError as err:
        logger.warning("[Updater] Network error while fetching latest.json: %s", err)
    except TimeoutError:
        logger.warning("[Updater] Timeout while fetching latest.json.")
    except json.JSONDecodeError as err:
        logger.warning("[Updater] latest.json could not be parsed: %s", err)
    except Exception as err:
        logger.exception("[Updater] Unexpected latest.json fetch failure: %s", err)
    return None


def _get_latest_update_metadata():
    manifest = _get_latest_manifest()
    if manifest is not None:
        return {
            "version": manifest["version"],
            "release_url": manifest["release_url"],
            "manifest": manifest,
            "release_data": None,
        }

    release = _get_latest_release()
    if not release:
        return None

    version = _normalize_version_tag(release.get("tag_name"))
    if version is None:
        logger.warning("[Updater] Ignoring release with invalid version tag: %s", release.get("tag_name"))
        return None

    release_url = str(release.get("html_url") or f"{RELEASES_URL}/latest").strip()
    return {
        "version": version,
        "release_url": release_url,
        "manifest": None,
        "release_data": release,
    }


def _select_asset_by_names(release_data, candidate_names):
    if not isinstance(release_data, dict):
        return None
    assets = release_data.get("assets") or []
    if not assets:
        return None

    lower_map = {}
    for asset in assets:
        name = str(asset.get("name", ""))
        lower_map[name.lower()] = asset

    for name in candidate_names:
        selected = lower_map.get(str(name).lower())
        if selected is not None:
            return selected
    return None


def _select_installer_asset(release_data):
    if not isinstance(release_data, dict):
        return None
    assets = release_data.get("assets") or []
    tag = str(release_data.get("tag_name", "")).strip()
    preferred = f"phantomrecoilsetup_{tag}.exe".lower() if tag else ""
    for asset in assets:
        name = str(asset.get("name", "")).strip()
        lowered = name.lower()
        if preferred and lowered == preferred:
            return asset
    for asset in assets:
        name = str(asset.get("name", "")).strip()
        if re.match(r"^PhantomRecoilSetup_.*\.exe$", name, flags=re.IGNORECASE):
            return asset
    return None


def _select_checksum_asset(release_data):
    return _select_asset_by_names(release_data, ["SHA256SUMS.txt"])


def _select_portable_asset(release_data):
    exe_name = os.path.basename(sys.executable)
    candidates = [exe_name, "Phantom_Recoil_Standalone.exe", "Phantom_Recoil.exe"]
    return _select_asset_by_names(release_data, candidates)


def _download_asset_to_temp(asset):
    url = str(asset.get("browser_download_url") or asset.get("url") or "").strip()
    name = str(asset.get("name", "")).strip() or "download.bin"
    if not url:
        raise RuntimeError(f"Asset {name!r} missing browser_download_url")

    _, ext = os.path.splitext(name)
    fd, temp_path = tempfile.mkstemp(prefix="phantom_recoil_update_", suffix=ext)
    os.close(fd)
    req = urllib.request.Request(url, headers={"User-Agent": UPDATER_USER_AGENT})

    with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response, open(temp_path, "wb") as handle:
        shutil.copyfileobj(response, handle)
    return temp_path


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest().lower()


def _parse_sha256sums(text):
    result = {}
    for raw_line in str(text).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # CI format: "filename hash"
        match_file_hash = re.match(r"^(.+?)\s+([A-Fa-f0-9]{64})$", line)
        if match_file_hash:
            name = match_file_hash.group(1).strip()
            file_hash = match_file_hash.group(2).lower()
            result[name] = file_hash
            continue

        # Common format: "hash filename" or "hash *filename"
        match_hash_file = re.match(r"^([A-Fa-f0-9]{64})\s+\*?(.+)$", line)
        if match_hash_file:
            file_hash = match_hash_file.group(1).lower()
            name = match_hash_file.group(2).strip()
            result[name] = file_hash
            continue

    return result


def _verify_asset_checksum(release_data, asset_name, downloaded_path, checksum_asset_override=None):
    checksum_asset = checksum_asset_override or _select_checksum_asset(release_data)
    if checksum_asset is None:
        logger.warning("[Updater] SHA256SUMS.txt not found in release assets. Skipping checksum verification.")
        return True

    checksum_path = None
    try:
        checksum_path = _download_asset_to_temp(checksum_asset)
        with open(checksum_path, "r", encoding="utf-8", errors="replace") as handle:
            checksums = _parse_sha256sums(handle.read())

        expected = checksums.get(asset_name)
        if not expected:
            logger.warning("[Updater] No checksum entry for asset %s. Skipping checksum verification.", asset_name)
            return True

        actual = _sha256_file(downloaded_path)
        if actual != expected:
            logger.error("[Updater] Checksum mismatch for %s.", asset_name)
            logger.error("[Updater] Expected: %s", expected)
            logger.error("[Updater] Actual:   %s", actual)
            return False
        return True
    except Exception as err:
        logger.warning("[Updater] Checksum verification failed: %s", err)
        return False
    finally:
        if checksum_path and os.path.exists(checksum_path):
            try:
                os.remove(checksum_path)
            except OSError:
                pass


def _verify_asset_hash_inline(asset, downloaded_path):
    expected = _normalize_sha256(asset.get("sha256"))
    if expected is None:
        return None
    actual = _sha256_file(downloaded_path)
    if actual != expected:
        logger.error("[Updater] Inline checksum mismatch for %s.", asset.get("name"))
        logger.error("[Updater] Expected: %s", expected)
        logger.error("[Updater] Actual:   %s", actual)
        return False
    return True


def _verify_downloaded_asset(asset, downloaded_path, release_data=None, checksum_asset=None):
    inline_result = _verify_asset_hash_inline(asset, downloaded_path)
    if inline_result is not None:
        return inline_result

    if release_data is not None or checksum_asset is not None:
        return _verify_asset_checksum(
            release_data,
            str(asset.get("name", "")),
            downloaded_path,
            checksum_asset_override=checksum_asset,
        )

    logger.warning(
        "[Updater] No checksum metadata available for %s. Proceeding without integrity check.",
        asset.get("name"),
    )
    return True


def _get_manifest_asset(manifest, key):
    if not isinstance(manifest, dict):
        return None
    assets = manifest.get("assets")
    if not isinstance(assets, dict):
        return None
    asset = assets.get(key)
    if not isinstance(asset, dict):
        return None
    return asset


def _can_write_to_directory(path):
    try:
        os.makedirs(path, exist_ok=True)
        probe_path = os.path.join(path, f".update_probe_{os.getpid()}.tmp")
        with open(probe_path, "w", encoding="utf-8") as handle:
            handle.write("ok")
        os.remove(probe_path)
        return True
    except Exception:
        return False


def _spawn_detached(command):
    creationflags = 0
    creationflags |= int(getattr(subprocess, "DETACHED_PROCESS", 0))
    creationflags |= int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))

    subprocess.Popen(
        command,
        close_fds=True,
        creationflags=creationflags,
    )


def _schedule_self_replace(downloaded_exe, target_exe):
    script = r"""param(
    [int]$OldPid,
    [string]$TargetExe,
    [string]$DownloadedExe
)
$ErrorActionPreference = 'Stop'
$deadline = (Get-Date).AddSeconds(45)
while ((Get-Process -Id $OldPid -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 250
}
Copy-Item -LiteralPath $DownloadedExe -Destination $TargetExe -Force
Start-Sleep -Milliseconds 250
Start-Process -FilePath $TargetExe
Remove-Item -LiteralPath $DownloadedExe -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
"""
    fd, script_path = tempfile.mkstemp(prefix="phantom_recoil_apply_update_", suffix=".ps1")
    os.close(fd)
    with open(script_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(script)

    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-WindowStyle",
        "Hidden",
        "-File",
        script_path,
        "-OldPid",
        str(os.getpid()),
        "-TargetExe",
        target_exe,
        "-DownloadedExe",
        downloaded_exe,
    ]
    _spawn_detached(cmd)
    return True


def _start_silent_installer(installer_path):
    cmd = [
        installer_path,
        "/SP-",
        "/VERYSILENT",
        "/NORESTART",
        "/CLOSEAPPLICATIONS",
    ]
    _spawn_detached(cmd)
    return True


def _launch_user_local_copy(downloaded_exe, exe_name):
    base = os.getenv("LOCALAPPDATA") or tempfile.gettempdir()
    update_dir = os.path.join(base, "PhantomRecoil", "updates")
    os.makedirs(update_dir, exist_ok=True)

    target_exe = os.path.join(update_dir, exe_name)
    shutil.copy2(downloaded_exe, target_exe)
    _spawn_detached([target_exe])
    return target_exe


def check_for_updates():
    """
    Checks GitHub for new releases.
    Returns (release_url, latest_version) if an update is available, else (None, None).
    """
    metadata = _get_latest_update_metadata()
    if not metadata:
        return None, None

    latest_version = metadata["version"]

    if latest_version and _is_newer_version(__version__, latest_version):
        release_url = metadata["release_url"]
        return release_url, latest_version
    return None, None


def _apply_update(release_data, latest_version, manifest=None):
    if not getattr(sys, "frozen", False):
        logger.info("[Updater] Running from source. Skipping auto-update apply.")
        return {"updated": False, "should_exit": False, "reason": "source-run"}

    portable_asset = _get_manifest_asset(manifest, "portable") or _select_portable_asset(release_data)
    installer_asset = _get_manifest_asset(manifest, "installer") or _select_installer_asset(release_data)
    checksums_asset = _get_manifest_asset(manifest, "checksums")
    exe_path = os.path.abspath(sys.executable)
    exe_dir = os.path.dirname(exe_path)

    if portable_asset is not None:
        try:
            logger.info("[Updater] Downloading update asset: %s", portable_asset.get("name"))
            downloaded = _download_asset_to_temp(portable_asset)

            if not _verify_downloaded_asset(
                portable_asset,
                downloaded,
                release_data=release_data,
                checksum_asset=checksums_asset,
            ):
                try:
                    os.remove(downloaded)
                except OSError:
                    pass
                return {"updated": False, "should_exit": False, "reason": "checksum-failed"}

            if _can_write_to_directory(exe_dir):
                _schedule_self_replace(downloaded, exe_path)
                logger.info("[Updater] Scheduled self-replace update to %s.", latest_version)
                return {"updated": True, "should_exit": True, "mode": "self-replace", "version": latest_version}

            # Fallback for non-writable install locations (e.g. Program Files without elevation):
            # run the latest binary from user-local app data.
            user_copy = _launch_user_local_copy(downloaded, os.path.basename(exe_path))
            logger.warning(
                "[Updater] No write permissions for %s. Launched user-local updated binary: %s",
                exe_dir,
                user_copy,
            )
            try:
                os.remove(downloaded)
            except OSError:
                pass
            return {"updated": True, "should_exit": True, "mode": "user-local-fallback", "version": latest_version}
        except Exception as err:
            logger.warning("[Updater] Portable update path failed: %s", err)

    if installer_asset is not None:
        try:
            logger.info("[Updater] Downloading installer asset: %s", installer_asset.get("name"))
            installer_path = _download_asset_to_temp(installer_asset)

            if not _verify_downloaded_asset(
                installer_asset,
                installer_path,
                release_data=release_data,
                checksum_asset=checksums_asset,
            ):
                try:
                    os.remove(installer_path)
                except OSError:
                    pass
                return {"updated": False, "should_exit": False, "reason": "checksum-failed"}

            _start_silent_installer(installer_path)
            logger.info("[Updater] Started silent installer update to %s.", latest_version)
            return {"updated": True, "should_exit": True, "mode": "installer", "version": latest_version}
        except Exception as err:
            logger.warning("[Updater] Installer update path failed: %s", err)

    return {"updated": False, "should_exit": False, "reason": "no-usable-asset"}


def run_auto_updater():
    """
    Checks for updates and applies them automatically for frozen builds.

    Returns a dict:
      - updated: bool
      - should_exit: bool (current process should exit to let updater continue)
      - mode/reason/version: additional metadata
    """
    try:
        logger.info("[Updater] Checking for updates (Current: %s)...", __version__)
        metadata = _get_latest_update_metadata()
        if not metadata:
            return {"updated": False, "should_exit": False, "reason": "release-unavailable"}

        latest_version = metadata["version"]

        if not _is_newer_version(__version__, latest_version):
            logger.info("[Updater] No newer release available.")
            return {"updated": False, "should_exit": False, "reason": "up-to-date"}

        logger.info("[Updater] New version found: %s (Current: %s)", latest_version, __version__)
        return _apply_update(
            metadata.get("release_data"),
            latest_version,
            manifest=metadata.get("manifest"),
        )
    except Exception as err:
        logger.exception("[Updater] Unexpected failure in auto-updater: %s", err)
        return {"updated": False, "should_exit": False, "reason": "unexpected-error"}
