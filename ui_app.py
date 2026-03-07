import webview
import threading
import os
from macro import RecoilMacro
import win32con
import ctypes
import sys
import updater
import math
import logging


logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

class Api:
    def __init__(self):
        self.macro = RecoilMacro()
        self.window = None
        
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

    def shutdown(self):
        logger.info("[Backend] Shutdown requested, stopping macro loop...")
        self.macro.stop()
        if self.macro_thread.is_alive():
            self.macro_thread.join(timeout=2.0)
            if self.macro_thread.is_alive():
                logger.warning("[Backend] Macro thread did not stop within timeout.")
            else:
                logger.info("[Backend] Macro thread stopped.")
        
    def get_caps_state(self):
        """Called by Javascript polling interval to safely get state without threading crashes"""
        try:
            return bool(ctypes.windll.user32.GetKeyState(win32con.VK_CAPITAL) & 0x0001)
        except Exception:
            return False

if __name__ == '__main__':
    # 1. Start GitHub Updater in background thread! This prevents the 5-sec API timeout from freezing the app start.
    threading.Thread(target=updater.run_auto_updater, daemon=True).start()

    api = Api()
    
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
    
    # Create the pywebview OS Window wrapping our beautiful web folder
    window = webview.create_window(
        'Phantom Recoil', 
        url=html_file, 
        js_api=api,
        width=1100, 
        height=700,
        min_size=(900, 550),
        background_color='#09090b',
        icon=icon_file
    )
    api.set_window(window)

    # Ensure background loop is stopped when the UI is closed.
    if hasattr(window, 'events') and hasattr(window.events, 'closed'):
        window.events.closed += lambda: api.shutdown()

    # private_mode=False ensures localStorage (favorites, DPI) isn't wiped on exit
    try:
        webview.start(private_mode=False)
    finally:
        api.shutdown()
