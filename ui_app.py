import webview
import threading
import os
import inspect
from macro import RecoilMacro
import win32con
import ctypes
import sys
import updater
import math
import logging
import tempfile
import time
import json
import faulthandler


logger = logging.getLogger(__name__)
DIAGNOSTIC_MODE = True
DIAGNOSTIC_DUMP_SECONDS = 45


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

    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    logger.info('[Startup] Diagnostic log file: %s', log_path)
    return log_path

class Api:
    def __init__(self):
        self.macro = RecoilMacro()
        self.window = None
        self.last_ping_ts = time.time()
        self.last_ping_payload = None
        self._ping_lock = threading.Lock()
        
        # Start the background polling thread.
        self.macro_thread = threading.Thread(target=self.macro.start, daemon=True)
        self.macro_thread.start()

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
        self.window = window

    def set_recoil(self, x, y):
        safe_x = self._to_finite_number(x, default=0.0)
        safe_y = self._to_finite_number(y, default=0.0)
        # Clamp to a sane range to avoid runaway movement due to malformed client input.
        safe_x = max(-100.0, min(100.0, safe_x))
        safe_y = max(-100.0, min(100.0, safe_y))

        logger.info("[Backend] Profile selected -> X:%s, Y:%s", safe_x, safe_y)
        self.macro.update_recoil(safe_x, safe_y)

    def set_multiplier(self, mult):
        safe_mult = self._to_finite_number(mult, default=0.5)
        safe_mult = max(0.01, min(1.0, safe_mult))
        logger.info("[Backend] Intensity set -> %s", safe_mult)
        self.macro.set_multiplier(safe_mult)

    def get_caps_state(self):
        """Called by JavaScript polling to safely read CapsLock state."""
        try:
            return bool(ctypes.windll.user32.GetKeyState(win32con.VK_CAPITAL) & 0x0001)
        except Exception:
            return False

    def ping(self, payload=None):
        with self._ping_lock:
            self.last_ping_ts = time.time()
            self.last_ping_payload = payload
        return {'ok': True, 'ts': self.last_ping_ts}

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
            'macro': self.macro.get_state_snapshot(),
        }

    def shutdown(self):
        logger.info("[Backend] Shutdown requested, stopping macro loop...")
        self.macro.stop()
        if self.macro_thread.is_alive():
            self.macro_thread.join(timeout=2.0)
            if self.macro_thread.is_alive():
                logger.warning("[Backend] Macro thread did not stop within timeout.")
            else:
                logger.info("[Backend] Macro thread stopped.")


def start_diagnostic_watchdog(api):
    def watchdog_loop():
        while True:
            try:
                time.sleep(5)
                status = api.get_diag_status()
                since_ping = status['since_ping_seconds']
                if since_ping > 15:
                    logger.warning('[Diag] Frontend heartbeat stale: %.2fs | macro=%s', since_ping, status['macro'])
            except Exception as err:
                logger.exception('[Diag] Watchdog failure: %s', err)

    thread = threading.Thread(target=watchdog_loop, daemon=True)
    thread.start()
    return thread

if __name__ == '__main__':
    log_path = setup_logging()

    if DIAGNOSTIC_MODE:
        try:
            with open(log_path, 'a', encoding='utf-8') as dump_file:
                faulthandler.enable(file=dump_file, all_threads=True)
                faulthandler.dump_traceback_later(DIAGNOSTIC_DUMP_SECONDS, repeat=True, file=dump_file)
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

    window = webview.create_window('Phantom Recoil', **window_kwargs)
    api.set_window(window)

    # Ensure background loop is stopped when the UI is closed.
    if hasattr(window, 'events') and hasattr(window.events, 'closed'):
        window.events.closed += lambda: api.shutdown()

    # private_mode=False ensures localStorage (favorites, DPI) isn't wiped on exit
    try:
        webview.start(private_mode=False)
    finally:
        api.shutdown()
        if DIAGNOSTIC_MODE:
            try:
                faulthandler.cancel_dump_traceback_later()
            except Exception:
                pass
