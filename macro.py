import time
import win32api
import win32con
import random
import threading
import ctypes
import math
import logging


logger = logging.getLogger(__name__)

# Keys whose active state is a toggle (on/off) rather than momentary press.
TOGGLE_KEYS = frozenset({win32con.VK_CAPITAL, win32con.VK_NUMLOCK, win32con.VK_SCROLL})

# Human-readable names for supported hotkeys.
VK_NAMES = {
    0x14: 'CapsLock',
    0x90: 'NumLock',
    0x91: 'ScrollLock',
    0x70: 'F1', 0x71: 'F2', 0x72: 'F3', 0x73: 'F4',
    0x74: 'F5', 0x75: 'F6', 0x76: 'F7', 0x77: 'F8',
    0x78: 'F9', 0x79: 'F10', 0x7A: 'F11', 0x7B: 'F12',
}

# Only these VK codes may be used as hotkey.
ALLOWED_HOTKEY_VKS = frozenset(VK_NAMES.keys())

# R6 Siege process names (DirectX and Vulkan).
R6_PROCESS_NAMES = frozenset({'RainbowSix.exe', 'RainbowSix_Vulkan.exe'})

# How often (seconds) to re-check if R6 is running.
GAME_CHECK_INTERVAL = 5.0

# Windows SystemParametersInfo codes for pointer settings.
_SPI_GETMOUSESPEED = 0x0070
_SPI_GETMOUSE = 0x0003

# Default Windows pointer speed (corresponds to 6/11 on the slider).
POINTER_SPEED_DEFAULT = 10


# ── SendInput structures ──────────────────────────────────────────────────────
# SendInput is the modern, preferred API over the deprecated mouse_event().
# It bypasses some legacy input filtering and is more reliable across
# different Windows versions and anti-cheat configurations.

class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ('dx',          ctypes.c_long),
        ('dy',          ctypes.c_long),
        ('mouseData',   ctypes.c_ulong),
        ('dwFlags',     ctypes.c_ulong),
        ('time',        ctypes.c_ulong),
        ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [('mi', _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [
        ('type',   ctypes.c_ulong),
        ('_input', _INPUT_UNION),
    ]


_INPUT_MOUSE = 0
_MOUSEEVENTF_MOVE = 0x0001


def _send_relative_mouse_move(dx: int, dy: int) -> None:
    """Inject a relative mouse movement via SendInput (modern replacement for mouse_event)."""
    inp = _INPUT(type=_INPUT_MOUSE)
    inp._input.mi = _MOUSEINPUT(
        dx=dx,
        dy=dy,
        mouseData=0,
        dwFlags=_MOUSEEVENTF_MOVE,
        time=0,
        dwExtraInfo=None,
    )
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


# ── Windows system info helpers ───────────────────────────────────────────────

def get_pointer_speed() -> int:
    """Read the Windows pointer speed setting (1–20, default 10 = 6/11 on slider)."""
    try:
        speed = ctypes.c_int(POINTER_SPEED_DEFAULT)
        ctypes.windll.user32.SystemParametersInfoW(_SPI_GETMOUSESPEED, 0, ctypes.byref(speed), 0)
        return int(speed.value)
    except Exception:
        return POINTER_SPEED_DEFAULT


def get_enhance_pointer_precision() -> bool:
    """Return True if 'Enhance Pointer Precision' (mouse acceleration) is enabled."""
    try:
        params = (ctypes.c_int * 3)()
        ctypes.windll.user32.SystemParametersInfoW(_SPI_GETMOUSE, 0, params, 0)
        return bool(params[2])
    except Exception:
        return False


class RecoilMacro:
    def __init__(self):
        self.recoil_x = 0
        self.recoil_y = 0
        self.multiplier = 0.5
        self.running = False
        self.hotkey_vk = win32con.VK_CAPITAL
        self._state_lock = threading.Lock()

        # Accumulators allow for sub-pixel smooth movements
        # when intensity multiplier creates float values.
        self.accumulated_x = 0.0
        self.accumulated_y = 0.0
        self.is_active = False

        # Game detection state.
        self._game_running = True   # optimistic default so macro works if psutil absent
        self._last_game_check = 0.0

    def _sanitize_number(self, value, default=0.0):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return float(default)
        if not math.isfinite(number):
            return float(default)
        return number

    def _check_hotkey_active(self, vk):
        """Return True if the configured hotkey is currently active."""
        if vk in TOGGLE_KEYS:
            return bool(ctypes.windll.user32.GetKeyState(vk) & 0x0001)
        return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)

    def _is_game_running(self):
        """Return True if a Rainbow Six Siege process is running."""
        try:
            import psutil  # type: ignore
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] in R6_PROCESS_NAMES:
                    return True
            return False
        except Exception:
            # psutil unavailable or access denied — assume game is running.
            return True

    def update_recoil(self, x, y):
        """Updates the recoil profile."""
        safe_x = self._sanitize_number(x, default=0.0)
        safe_y = self._sanitize_number(y, default=0.0)
        with self._state_lock:
            self.recoil_x = safe_x
            self.recoil_y = safe_y

    def set_multiplier(self, mult):
        """Sets the intensity smoothing multiplier."""
        safe_mult = self._sanitize_number(mult, default=0.5)
        safe_mult = max(0.01, min(1.0, safe_mult))
        with self._state_lock:
            self.multiplier = safe_mult

    def set_hotkey(self, vk_code):
        """Change the activation hotkey. Only keys in ALLOWED_HOTKEY_VKS are accepted."""
        vk = int(vk_code) & 0xFF
        if vk not in ALLOWED_HOTKEY_VKS:
            logger.warning("[Macro] Rejected hotkey VK 0x%02X — not in allowed set.", vk)
            return False
        with self._state_lock:
            self.hotkey_vk = vk
        logger.info("[Macro] Hotkey changed to %s (VK 0x%02X).", VK_NAMES.get(vk, '?'), vk)
        return True

    def stop(self):
        """Stops the macro loop gracefully."""
        with self._state_lock:
            self.running = False

    def get_state_snapshot(self):
        """Return a thread-safe state snapshot for diagnostics."""
        with self._state_lock:
            return {
                'running': self.running,
                'recoil_x': self.recoil_x,
                'recoil_y': self.recoil_y,
                'multiplier': self.multiplier,
                'is_active': self.is_active,
                'hotkey_vk': self.hotkey_vk,
                'hotkey_name': VK_NAMES.get(self.hotkey_vk, f'VK_0x{self.hotkey_vk:02X}'),
                'game_running': self._game_running,
            }

    def start(self):
        """Starts the main polling loop for mouse events."""
        with self._state_lock:
            self.running = True

        while True:
            with self._state_lock:
                if not self.running:
                    break
                hotkey_vk = self.hotkey_vk
            try:
                # Periodically verify that R6 Siege is actually running.
                now = time.time()
                if now - self._last_game_check >= GAME_CHECK_INTERVAL:
                    self._last_game_check = now
                    self._game_running = self._is_game_running()
                    if not self._game_running:
                        logger.info("[Macro] R6 Siege not detected — macro suspended.")

                if not self._game_running:
                    with self._state_lock:
                        self.is_active = False
                    time.sleep(0.5)
                    continue

                # GetKeyState via ctypes ignores the thread message pump limitations.
                hotkey_active = self._check_hotkey_active(hotkey_vk)
                with self._state_lock:
                    self.is_active = hotkey_active
                    recoil_x = self.recoil_x
                    recoil_y = self.recoil_y
                    multiplier = self.multiplier

                if hotkey_active:
                    # Check if Right Mouse Button is pressed (Aiming).
                    rmb_pressed = win32api.GetAsyncKeyState(win32con.VK_RBUTTON) < 0

                    if rmb_pressed:
                        # Check if Left Mouse Button is pressed (Shooting).
                        lmb_pressed = win32api.GetAsyncKeyState(win32con.VK_LBUTTON) < 0

                        if lmb_pressed:
                            # Original Lua logic: MoveMouseRelative(recoilX - 1, recoilY)
                            # We apply the multiplier to lessen aggressive pulling.
                            dx_target = (recoil_x - 1) * multiplier
                            dy_target = recoil_y * multiplier

                            # Accumulate decimals to ensure smooth slow pull instead of jitter.
                            self.accumulated_x += dx_target
                            self.accumulated_y += dy_target

                            move_x = int(self.accumulated_x)
                            move_y = int(self.accumulated_y)

                            # Only move mouse if there's actually a full pixel to move.
                            if move_x != 0 or move_y != 0:
                                _send_relative_mouse_move(move_x, move_y)
                                self.accumulated_x -= move_x
                                self.accumulated_y -= move_y

                            # Random sleep between 2 and 3 ms as per Lua script: Sleep(math.random(2,3))
                            time.sleep(random.uniform(0.002, 0.003))
                            continue

                    # Reset accumulators if not actively firing.
                    self.accumulated_x = 0.0
                    self.accumulated_y = 0.0

                    # Keep aim-ready mode responsive, but avoid spinning too aggressively.
                    time.sleep(0.002)
                    continue

                # Hotkey is off: use a slower poll to reduce background CPU pressure.
                time.sleep(0.006)
                continue
            except Exception as e:
                logger.exception("[Macro Error] Polling loop failure: %s", e)

            # Sleep 1ms to prevent 100% CPU utilization after an exception.
            time.sleep(0.001)
