import time
import win32api
import win32con
import random
import threading
import ctypes
from ctypes import wintypes
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
_MOUSEEVENTF_MOVE      = 0x0001
_MOUSEEVENTF_LEFTDOWN  = 0x0002
_MOUSEEVENTF_LEFTUP    = 0x0004

_WH_MOUSE_LL = 14
_WM_LBUTTONDOWN = 0x0201
_WM_LBUTTONUP = 0x0202
_WM_QUIT = 0x0012
_LLMHF_INJECTED = 0x00000001


class _POINT(ctypes.Structure):
    _fields_ = [
        ('x', wintypes.LONG),
        ('y', wintypes.LONG),
    ]


class _MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ('pt', _POINT),
        ('mouseData', wintypes.DWORD),
        ('flags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ctypes.c_void_p),
    ]


_LOW_LEVEL_MOUSE_PROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
)

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
_user32.SetWindowsHookExW.argtypes = (ctypes.c_int, _LOW_LEVEL_MOUSE_PROC, ctypes.c_void_p, wintypes.DWORD)
_user32.SetWindowsHookExW.restype = ctypes.c_void_p
_user32.CallNextHookEx.argtypes = (ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
_user32.CallNextHookEx.restype = ctypes.c_ssize_t
_user32.UnhookWindowsHookEx.argtypes = (ctypes.c_void_p,)
_user32.UnhookWindowsHookEx.restype = wintypes.BOOL
_user32.PostThreadMessageW.argtypes = (wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
_user32.PostThreadMessageW.restype = wintypes.BOOL


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


def _send_mouse_button(flags: int) -> None:
    """Inject a mouse button event via SendInput (e.g. LEFTDOWN / LEFTUP)."""
    inp = _INPUT(type=_INPUT_MOUSE)
    inp._input.mi = _MOUSEINPUT(
        dx=0,
        dy=0,
        mouseData=0,
        dwFlags=flags,
        time=0,
        dwExtraInfo=None,
    )
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def _send_button_with_move(flags: int, dx: int, dy: int) -> None:
    """Batch a button event + optional relative move in one SendInput call.

    Real gaming mice deliver movement delta and button state changes in the
    same USB HID report, so they appear as a compound input event rather
    than two consecutive single-event calls.  Replicating this structure
    makes the injection pattern harder to distinguish from hardware.
    """
    if dx or dy:
        inputs = (_INPUT * 2)()
        inputs[0].type = _INPUT_MOUSE
        inputs[0]._input.mi = _MOUSEINPUT(
            dx=dx, dy=dy, mouseData=0, dwFlags=_MOUSEEVENTF_MOVE, time=0, dwExtraInfo=None,
        )
        inputs[1].type = _INPUT_MOUSE
        inputs[1]._input.mi = _MOUSEINPUT(
            dx=0, dy=0, mouseData=0, dwFlags=flags, time=0, dwExtraInfo=None,
        )
        ctypes.windll.user32.SendInput(2, inputs, ctypes.sizeof(_INPUT))
    else:
        _send_mouse_button(flags)


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

        # Rapid fire state — for semi-auto weapons (DMRs).
        # When enabled the loop injects timed click sequences instead of
        # continuously compensating while LMB is physically held.
        self.rapid_fire = False
        self.fire_interval = 0.30  # unused for timing, kept for API compat

        # Tracks whether the last synthetic event we sent was LEFTDOWN.
        # Used to guarantee a matching LEFTUP is always sent when leaving
        # the rapid fire state — prevents the "stuck button" auto-fire bug.
        self._rf_btn_down = False
        self._rf_hold_neutralized = False

        # Human-behavior simulation counters for anti-cheat evasion.
        # _rf_shot_count: shots fired in current burst.
        # _rf_next_fatigue: shot count at which next fatigue pause triggers.
        self._rf_shot_count = 0
        self._rf_next_fatigue = random.randint(7, 14)

        # Track the real physical LMB state separately from injected clicks.
        self._physical_lmb_pressed = False
        self._mouse_hook = None
        self._mouse_hook_proc = None
        self._mouse_hook_thread = None
        self._mouse_hook_thread_id = 0
        self._mouse_hook_ready = threading.Event()
        self._mouse_hook_available = False

        # Game detection state.
        self._game_running = True   # optimistic default so macro works if psutil absent
        self._last_game_check = 0.0

        # Scheduling diagnostics — set during start().
        self.timer_resolution_set = False   # True if timeBeginPeriod(1) succeeded
        self.thread_priority_set = False    # True if THREAD_PRIORITY_HIGHEST succeeded

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

    def set_rapid_fire(self, enabled: bool, interval_ms: float = 300.0) -> None:
        """Enable or disable rapid fire mode for semi-auto weapons (DMRs).

        interval_ms: time between shots in milliseconds (clamped 50–2000).
        """
        safe_interval = self._sanitize_number(interval_ms, default=300.0)
        safe_interval = max(50.0, min(2000.0, safe_interval))
        with self._state_lock:
            self.rapid_fire = bool(enabled)
            self.fire_interval = safe_interval / 1000.0
        if not enabled:
            self._rf_reset_cycle()
        logger.info("[Macro] Rapid fire: enabled=%s interval=%.0fms", bool(enabled), safe_interval)

    def _rf_release(self) -> None:
        """Send LEFTUP if a synthetic LEFTDOWN is outstanding from rapid fire.

        Must be called whenever the macro leaves the active-firing state so the
        game never sees an unpaired LEFTDOWN (which would cause permanent auto-fire).
        """
        if self._rf_btn_down:
            _send_mouse_button(_MOUSEEVENTF_LEFTUP)
            self._rf_btn_down = False

    def _rf_reset_cycle(self) -> None:
        """Clear any rapid-fire click state and forget the current burst."""
        self._rf_release()
        self._rf_hold_neutralized = False
        self._rf_shot_count = 0
        self._rf_next_fatigue = random.randint(7, 14)

    def _handle_mouse_hook_event(self, message: int, flags: int) -> None:
        """Update physical LMB state from the low-level mouse hook."""
        if flags & _LLMHF_INJECTED:
            return
        if message == _WM_LBUTTONDOWN:
            with self._state_lock:
                self._physical_lmb_pressed = True
        elif message == _WM_LBUTTONUP:
            with self._state_lock:
                self._physical_lmb_pressed = False

    def _mouse_hook_callback(self, n_code, w_param, l_param):
        """Low-level mouse hook that ignores our own injected clicks."""
        if n_code >= 0 and l_param:
            hook = ctypes.cast(l_param, ctypes.POINTER(_MSLLHOOKSTRUCT)).contents
            self._handle_mouse_hook_event(int(w_param), int(hook.flags))
        return _user32.CallNextHookEx(self._mouse_hook, n_code, w_param, l_param)

    def _mouse_hook_loop(self) -> None:
        """Run the low-level mouse hook on a dedicated message-pump thread."""
        self._mouse_hook_ready.clear()
        self._mouse_hook_thread_id = _kernel32.GetCurrentThreadId()
        self._mouse_hook_proc = _LOW_LEVEL_MOUSE_PROC(self._mouse_hook_callback)
        hook = _user32.SetWindowsHookExW(
            _WH_MOUSE_LL,
            self._mouse_hook_proc,
            None,
            0,
        )
        with self._state_lock:
            self._mouse_hook = hook
            self._mouse_hook_available = bool(hook)
        if not hook:
            self._mouse_hook_thread_id = 0
            self._mouse_hook_proc = None
            logger.warning("[Macro] Could not install low-level mouse hook; falling back to GetAsyncKeyState.")
            self._mouse_hook_ready.set()
            return

        logger.info("[Macro] Low-level mouse hook installed for physical LMB tracking.")
        self._mouse_hook_ready.set()
        msg = wintypes.MSG()
        try:
            while True:
                result = _user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result == 0:
                    break
                if result == -1:
                    logger.warning("[Macro] Mouse hook message loop returned GetMessageW=-1.")
                    break
                _user32.TranslateMessage(ctypes.byref(msg))
                _user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            try:
                _user32.UnhookWindowsHookEx(hook)
            except Exception:
                logger.warning("[Macro] Failed to unhook low-level mouse hook.", exc_info=True)
            with self._state_lock:
                self._mouse_hook = None
                self._mouse_hook_available = False
                self._physical_lmb_pressed = False
            self._mouse_hook_thread_id = 0
            self._mouse_hook_proc = None
            logger.info("[Macro] Low-level mouse hook stopped.")

    def _ensure_mouse_hook(self) -> None:
        """Start physical mouse tracking once before the macro loop begins."""
        if self._mouse_hook_thread and self._mouse_hook_thread.is_alive():
            return
        self._physical_lmb_pressed = win32api.GetAsyncKeyState(win32con.VK_LBUTTON) < 0
        self._mouse_hook_thread = threading.Thread(target=self._mouse_hook_loop, daemon=True, name='mouse-hook')
        self._mouse_hook_thread.start()
        self._mouse_hook_ready.wait(timeout=1.0)

    def _stop_mouse_hook(self) -> None:
        """Stop the physical mouse tracking thread if it is running."""
        thread = self._mouse_hook_thread
        thread_id = self._mouse_hook_thread_id
        if thread_id:
            _user32.PostThreadMessageW(thread_id, _WM_QUIT, 0, 0)
        if thread and thread.is_alive():
            thread.join(timeout=1.0)
        self._mouse_hook_thread = None

    def _is_lmb_pressed(self) -> bool:
        """Read physical LMB state, falling back to GetAsyncKeyState if needed."""
        with self._state_lock:
            if self._mouse_hook_available:
                return self._physical_lmb_pressed
        return win32api.GetAsyncKeyState(win32con.VK_LBUTTON) < 0

    def _rf_prime_burst(self) -> None:
        """Neutralize the held physical button before injecting synthetic clicks."""
        if self._rf_hold_neutralized:
            return
        _send_mouse_button(_MOUSEEVENTF_LEFTUP)
        self._rf_btn_down = False
        self._rf_hold_neutralized = True

    def _rf_fire_shot(self, recoil_x: float, recoil_y: float, multiplier: float) -> None:
        """Fire one rapid-fire click with full human-behavior simulation.

        Timing model targets 6–13 shots/sec — the upper range of real human
        rapid-clicking — using triangular distributions, micro-tremor, fatigue
        simulation and rare fumbles to defeat statistical pattern analysis.
        """
        dx_target = (recoil_x - 1) * multiplier
        dy_target = recoil_y * multiplier
        self.accumulated_x += dx_target
        self.accumulated_y += dy_target
        move_x = int(self.accumulated_x)
        move_y = int(self.accumulated_y)

        # Micro-tremor: hands always have slight movement when clicking.
        # Applied ~25 % of shots; amplitude capped at ±1 px so it's subtle.
        if random.random() < 0.25:
            tremor_x = random.choice((-1, 0, 1))
            tremor_y = random.choice((-1, 0, 0, 1))
        else:
            tremor_x = tremor_y = 0

        try:
            # Bundle DOWN + optional tremor in one SendInput batch.
            _send_button_with_move(_MOUSEEVENTF_LEFTDOWN, tremor_x, tremor_y)
            self._rf_btn_down = True

            # Click-hold duration: triangular distribution (mode 42 ms).
            # Real human button-press measurements: 30–80 ms, peak ~45 ms.
            time.sleep(random.triangular(0.028, 0.075, 0.042))

            # Bundle UP + recoil compensation in one SendInput batch.
            _send_button_with_move(_MOUSEEVENTF_LEFTUP, move_x, move_y)
            self._rf_btn_down = False
            if move_x or move_y:
                self.accumulated_x -= move_x
                self.accumulated_y -= move_y
        except Exception:
            self._rf_release()
            raise

        # Reset accumulator — each semi-auto shot is independent.
        self.accumulated_x = 0.0
        self.accumulated_y = 0.0

        # Inter-shot gap: triangular distribution (mode 62 ms).
        # Gives ~6–13 shots/sec which matches fast but plausible human clicking.
        gap = random.triangular(0.045, 0.095, 0.062)

        # Fatigue simulation: after every N shots the finger needs a tiny rest.
        # N is randomised (7–14) so the period itself is unpredictable.
        self._rf_shot_count += 1
        if self._rf_shot_count >= self._rf_next_fatigue:
            gap += random.triangular(0.012, 0.048, 0.024)
            self._rf_shot_count = 0
            self._rf_next_fatigue = random.randint(7, 14)

        # Rare fumble (~1.5 %): a noticeable hesitation like a real misclick.
        if random.random() < 0.015:
            gap += random.uniform(0.065, 0.190)

        time.sleep(gap)

    def _sleep_interruptible(self, duration: float, step: float = 0.010) -> bool:
        """Sleep for *duration* seconds in small steps.

        Returns False immediately if the macro is stopped mid-sleep so the
        caller can break out of the polling loop cleanly.
        """
        elapsed = 0.0
        while elapsed < duration:
            t = min(step, duration - elapsed)
            time.sleep(t)
            elapsed += t
            if not self.running:   # racy but acceptable for a stop-check
                return False
        return True

    def stop(self):
        """Stops the macro loop gracefully."""
        with self._state_lock:
            self.running = False
        self._stop_mouse_hook()

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
                'rapid_fire': self.rapid_fire,
                'fire_interval_ms': round(self.fire_interval * 1000),
            }

    def start(self):
        """Starts the main polling loop for mouse events."""
        # ── Scheduling setup ─────────────────────────────────────────────────────
        # Three layers are needed for precise 2ms loop timing on all machines:
        #
        # 1. timeBeginPeriod(1): reduces Windows timer quantum from default 15.625ms
        #    to 1ms so time.sleep(0.002) actually sleeps ~2ms, not ~15ms.
        #    Without this, mouse moves fire at ~67Hz (jitter) instead of ~400Hz.
        #
        # 2. THREAD_PRIORITY_HIGHEST: prevents OS preemption mid-tick. At normal
        #    priority a game, AV scan, or GPU driver can delay this thread 5-20ms.
        #
        # 3. sys.setswitchinterval(0.001): reduces Python GIL check from 5ms to
        #    1ms so the macro thread re-acquires the GIL quickly after sleep,
        #    even if the UI thread is actively processing JS bridge calls.

        try:
            if ctypes.windll.winmm.timeBeginPeriod(1) == 0:  # TIMERR_NOERROR = 0
                self.timer_resolution_set = True
                logger.info("[Macro] Timer resolution set to 1ms.")
            else:
                logger.warning("[Macro] timeBeginPeriod(1) returned non-zero — falling back to system default.")
        except Exception:
            logger.warning("[Macro] Could not call timeBeginPeriod — winmm.dll unavailable.")

        try:
            _THREAD_PRIORITY_HIGHEST = 2
            ctypes.windll.kernel32.SetThreadPriority(
                ctypes.windll.kernel32.GetCurrentThread(), _THREAD_PRIORITY_HIGHEST
            )
            self.thread_priority_set = True
            logger.info("[Macro] Thread priority set to HIGHEST.")
        except Exception:
            logger.warning("[Macro] Could not set thread priority.")

        try:
            import sys as _sys
            _sys.setswitchinterval(0.001)
            logger.info("[Macro] GIL switch interval set to 1ms.")
        except Exception:
            logger.warning("[Macro] Could not set GIL switch interval.")

        self._ensure_mouse_hook()
        with self._state_lock:
            self.running = True

        try:
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
                        self._rf_reset_cycle()
                        self.accumulated_x = 0.0
                        self.accumulated_y = 0.0
                        time.sleep(0.5)
                        continue

                    # GetKeyState via ctypes ignores the thread message pump limitations.
                    hotkey_active = self._check_hotkey_active(hotkey_vk)
                    with self._state_lock:
                        self.is_active = hotkey_active
                        recoil_x = self.recoil_x
                        recoil_y = self.recoil_y
                        multiplier = self.multiplier
                        rapid_fire = self.rapid_fire

                    if hotkey_active:
                        # Check if Right Mouse Button is pressed (Aiming).
                        rmb_pressed = win32api.GetAsyncKeyState(win32con.VK_RBUTTON) < 0

                        if rmb_pressed:
                            # Check if Left Mouse Button is pressed (Shooting).
                            lmb_pressed = self._is_lmb_pressed()

                            if lmb_pressed:
                                if rapid_fire:
                                    # ── Ultra-fast rapid fire for semi-auto weapons ───────────
                                    self._rf_prime_burst()
                                    self._rf_fire_shot(recoil_x, recoil_y, multiplier)

                                else:
                                    self._rf_reset_cycle()
                                    # ── Normal recoil compensation ────────────────────────────
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

                        # Leaving firing state: release any synthetic LEFTDOWN first,
                        # then reset accumulators.
                        self._rf_reset_cycle()
                        self.accumulated_x = 0.0
                        self.accumulated_y = 0.0

                        # Keep aim-ready mode responsive, but avoid spinning too aggressively.
                        time.sleep(0.002)
                        continue

                    # Hotkey is off: release any outstanding synthetic button before idling.
                    self._rf_reset_cycle()
                    time.sleep(0.006)
                    continue
                except Exception as e:
                    logger.exception("[Macro Error] Polling loop failure: %s", e)

                # Sleep 1ms to prevent 100% CPU utilization after an exception.
                time.sleep(0.001)
        finally:
            # Ensure no synthetic LEFTDOWN is left hanging when the macro exits.
            self._rf_reset_cycle()
            self._stop_mouse_hook()
            if self.timer_resolution_set:
                try:
                    ctypes.windll.winmm.timeEndPeriod(1)
                    logger.info("[Macro] Timer resolution released.")
                except Exception:
                    pass
