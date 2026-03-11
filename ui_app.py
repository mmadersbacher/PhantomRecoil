import webview
import threading
import os
import inspect
from macro import RecoilMacro
import sys
import updater
import math
import logging
import logging.handlers
import tempfile
import time
import json
import faulthandler
import traceback
import platform
import uuid


logger = logging.getLogger(__name__)
DIAGNOSTIC_MODE = os.getenv('PHANTOM_RECOIL_DIAGNOSTIC', '1') != '0'
DIAGNOSTIC_DUMP_SECONDS = 45
PROCESS_SNAPSHOT_SECONDS = 10
APP_TITLE = f"Phantom Recoil {updater.__version__}"
DIAG_DUMP_FILE = None


def _safe_process_memory_mb():
    """Best effort process memory read for Windows diagnostics."""
    try:
        import psutil  # type: ignore

        rss_bytes = psutil.Process(os.getpid()).memory_info().rss
        return round(rss_bytes / (1024 * 1024), 2)
    except Exception:
        return None


def get_diagnostic_log_path():
    base = os.getenv('LOCALAPPDATA')
    if not base:
        base = tempfile.gettempdir()

    log_dir = os.path.join(base, 'PhantomRecoil', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, 'phantom_recoil_diagnostic.log')


def setup_logging():
    log_path = get_diagnostic_log_path()
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(name)s: %(message)s')

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8',
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    logger.info('[Startup] Diagnostic log file: %s', log_path)
    return log_path


def install_crash_hooks():
    """Capture uncaught exceptions from main and worker threads in diagnostics."""

    def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
        logger.critical(
            '[Crash] Uncaught exception: %s\n%s',
            exc_value,
            ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
        )

    sys.excepthook = handle_uncaught_exception

    def handle_thread_exception(args):
        logger.critical(
            '[Crash] Uncaught thread exception in %s: %s\n%s',
            getattr(args.thread, 'name', 'unknown-thread'),
            args.exc_value,
            ''.join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)),
        )

    if hasattr(threading, 'excepthook'):
        threading.excepthook = handle_thread_exception

class Api:
    def __init__(self):
        # Use underscore-prefixed internals so pywebview's API scanner does not
        # recursively traverse large native object graphs (window.native...).
        self._macro = RecoilMacro()
        self._window = None
        self.session_id = str(uuid.uuid4())
        self.started_at = time.time()
        self.last_ping_ts = time.time()
        self.last_ping_payload = None
        self._ping_lock = threading.Lock()

        logger.info('[Startup] Session=%s | App=%s | Python=%s | Platform=%s', self.session_id, APP_TITLE, sys.version.split()[0], platform.platform())
        
        # Start the background polling thread.
        self._macro_thread = threading.Thread(target=self._macro.start, daemon=True)
        self._macro_thread.start()

    @staticmethod
    def _to_finite_number(value, default=0.0):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return float(default)
        if not math.isfinite(number):
            return float(default)
        return number

    def set_window(self, window):
        self._window = window

    def set_recoil(self, x, y):
        safe_x = self._to_finite_number(x, default=0.0)
        safe_y = self._to_finite_number(y, default=0.0)
        # Clamp to a sane range to avoid runaway movement due to malformed client input.
        safe_x = max(-100.0, min(100.0, safe_x))
        safe_y = max(-100.0, min(100.0, safe_y))

        logger.info("[Backend] Profile selected -> X:%s, Y:%s", safe_x, safe_y)
        self._macro.update_recoil(safe_x, safe_y)

    def set_multiplier(self, mult):
        safe_mult = self._to_finite_number(mult, default=0.5)
        safe_mult = max(0.01, min(1.0, safe_mult))
        logger.info("[Backend] Intensity set -> %s", safe_mult)
        self._macro.set_multiplier(safe_mult)

    def get_hotkey_state(self):
        """Called by JavaScript polling to read the active hotkey state and game status."""
        try:
            with self._macro._state_lock:
                vk = self._macro.hotkey_vk
            active = self._macro._check_hotkey_active(vk)
            return {'active': active, 'game_running': self._macro._game_running}
        except Exception:
            return {'active': False, 'game_running': True}

    def ping(self, payload=None):
        with self._ping_lock:
            self.last_ping_ts = time.time()
            self.last_ping_payload = payload
        return {'ok': True, 'ts': self.last_ping_ts}

    def get_app_info(self):
        """Provides app metadata to the frontend for diagnostics and version labels."""
        return {
            'title': APP_TITLE,
            'version': updater.__version__,
            'session_id': self.session_id,
        }

    def log_client_event(self, level='info', message='', context=None):
        safe_message = str(message or '')[:300]
        safe_context = context if isinstance(context, dict) else {}

        try:
            context_text = json.dumps(safe_context, ensure_ascii=True)[:1000]
        except Exception:
            context_text = '{}'

        if level == 'error':
            logger.error('[Frontend] %s | context=%s', safe_message, context_text)
        elif level == 'warning':
            logger.warning('[Frontend] %s | context=%s', safe_message, context_text)
        else:
            logger.info('[Frontend] %s | context=%s', safe_message, context_text)

        return {'ok': True}

    def get_diag_status(self):
        with self._ping_lock:
            since_ping = time.time() - self.last_ping_ts
            payload = self.last_ping_payload
        return {
            'since_ping_seconds': round(since_ping, 3),
            'last_ping_payload': payload,
            'macro': self._macro.get_state_snapshot(),
            'uptime_seconds': round(time.time() - self.started_at, 3),
            'threads': threading.active_count(),
            'memory_mb': _safe_process_memory_mb(),
            'session_id': self.session_id,
        }

    def dump_diagnostics(self, reason='manual-request'):
        """Force a snapshot + traceback dump to aid freeze analysis."""
        safe_reason = str(reason or 'manual-request')[:200]
        status = self.get_diag_status()
        logger.warning('[Diag] Forced diagnostic dump requested: %s | status=%s', safe_reason, status)
        try:
            if DIAG_DUMP_FILE is not None:
                faulthandler.dump_traceback(file=DIAG_DUMP_FILE, all_threads=True)
            else:
                faulthandler.dump_traceback(all_threads=True)
        except Exception as err:
            logger.exception('[Diag] dump_diagnostics failed: %s', err)
            return {'ok': False, 'error': str(err)}
        return {'ok': True, 'reason': safe_reason}

    def get_hotkey(self):
        """Return current hotkey VK code and name."""
        from macro import VK_NAMES
        with self._macro._state_lock:
            vk = self._macro.hotkey_vk
        return {'vk_code': vk, 'name': VK_NAMES.get(vk, f'VK_0x{vk:02X}')}

    def set_hotkey(self, vk_code):
        """Set activation hotkey. Accepts only safe toggle/function keys."""
        try:
            vk = int(vk_code) & 0xFF
        except (TypeError, ValueError):
            return {'ok': False, 'error': 'Invalid VK code'}
        ok = self._macro.set_hotkey(vk)
        if ok:
            from macro import VK_NAMES
            logger.info("[Backend] Hotkey updated to VK 0x%02X", vk)
            return {'ok': True, 'vk_code': vk, 'name': VK_NAMES.get(vk, f'VK_0x{vk:02X}')}
        return {'ok': False, 'error': 'Key not in allowed set'}

    def shutdown(self):
        logger.info("[Backend] Shutdown requested, stopping macro loop...")
        self._macro.stop()
        if self._macro_thread.is_alive():
            self._macro_thread.join(timeout=2.0)
            if self._macro_thread.is_alive():
                logger.warning("[Backend] Macro thread did not stop within timeout.")
            else:
                logger.info("[Backend] Macro thread stopped.")


def start_diagnostic_watchdog(api):
    def watchdog_loop():
        last_snapshot_ts = 0.0
        while True:
            try:
                time.sleep(5)
                status = api.get_diag_status()
                since_ping = status['since_ping_seconds']
                if since_ping > 15:
                    logger.warning('[Diag] Frontend heartbeat stale: %.2fs | macro=%s', since_ping, status['macro'])
                    # Force immediate thread dump when UI heartbeat stalls.
                    if DIAG_DUMP_FILE is not None:
                        faulthandler.dump_traceback(file=DIAG_DUMP_FILE, all_threads=True)
                    else:
                        faulthandler.dump_traceback(all_threads=True)

                now = time.time()
                if now - last_snapshot_ts >= PROCESS_SNAPSHOT_SECONDS:
                    last_snapshot_ts = now
                    logger.info(
                        '[Diag] Snapshot session=%s uptime=%.2fs threads=%s memory_mb=%s',
                        status['session_id'],
                        status['uptime_seconds'],
                        status['threads'],
                        status['memory_mb'],
                    )
            except Exception as err:
                logger.exception('[Diag] Watchdog failure: %s', err)

    thread = threading.Thread(target=watchdog_loop, daemon=True)
    thread.start()
    return thread

if __name__ == '__main__':
    log_path = setup_logging()
    install_crash_hooks()

    if DIAGNOSTIC_MODE:
        try:
            # Keep the file handle open for the full process lifetime so faulthandler
            # never writes into a closed stream.
            DIAG_DUMP_FILE = open(log_path, 'a', encoding='utf-8')
            faulthandler.enable(file=DIAG_DUMP_FILE, all_threads=True)
            faulthandler.dump_traceback_later(DIAGNOSTIC_DUMP_SECONDS, repeat=True, file=DIAG_DUMP_FILE)
            logger.info('[Diag] faulthandler enabled with %ss interval.', DIAGNOSTIC_DUMP_SECONDS)
        except Exception as err:
            logger.warning('[Diag] Failed to enable faulthandler: %s', err)

    # 1. Start GitHub Updater in background thread! This prevents the 5-sec API timeout from freezing the app start.
    threading.Thread(target=updater.run_auto_updater, daemon=True).start()

    api = Api()
    if DIAGNOSTIC_MODE:
        start_diagnostic_watchdog(api)
    
    # 2. Resolve runtime path robustly for source and PyInstaller builds.
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base_path = os.path.dirname(__file__)
        
    html_file = os.path.join(base_path, 'web', 'index.html')
    icon_file = os.path.join(base_path, 'icon.ico')

    if not os.path.exists(html_file):
        logger.error("[Startup] Missing required UI file: %s", html_file)
        sys.exit(1)

    if not os.path.exists(icon_file):
        logger.warning("[Startup] icon.ico not found at %s. Continuing without custom icon.", icon_file)
        icon_file = None
    
    # Create a window with backward compatibility for pywebview variants
    # that do not implement the `icon` keyword argument.
    window_kwargs = {
        'url': html_file,
        'js_api': api,
        'width': 1100,
        'height': 700,
        'min_size': (900, 550),
        'background_color': '#09090b',
    }

    create_window_params = inspect.signature(webview.create_window).parameters
    if icon_file and 'icon' in create_window_params:
        window_kwargs['icon'] = icon_file
    elif icon_file:
        logger.info("[Startup] pywebview does not support 'icon' parameter. Continuing without custom icon.")

    window = webview.create_window(APP_TITLE, **window_kwargs)
    api.set_window(window)

    # Ensure background loop is stopped when the UI is closed.
    if hasattr(window, 'events') and hasattr(window.events, 'closed'):
        window.events.closed += lambda: api.shutdown()

    # private_mode=False ensures localStorage (favorites, DPI) isn't wiped on exit
    try:
        webview.start(private_mode=False)
    except Exception as err:
        logger.exception('[Startup] webview.start failed: %s', err)
        raise
    finally:
        api.shutdown()
        if DIAGNOSTIC_MODE:
            try:
                faulthandler.cancel_dump_traceback_later()
            except Exception:
                pass
            try:
                if DIAG_DUMP_FILE is not None:
                    DIAG_DUMP_FILE.flush()
                    DIAG_DUMP_FILE.close()
                    DIAG_DUMP_FILE = None
            except Exception:
                pass
