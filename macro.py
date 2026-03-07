import time
import win32api
import win32con
import random
import threading
import ctypes
import math
import logging


logger = logging.getLogger(__name__)

class RecoilMacro:
    def __init__(self):
        self.recoil_x = 0
        self.recoil_y = 0
        self.multiplier = 0.5
        self.running = False
        self._state_lock = threading.Lock()
        
        # Accumulators allow for sub-pixel smooth movements
        # when intensity multiplier creates float values
        self.accumulated_x = 0.0
        self.accumulated_y = 0.0
        self.is_active = False

    def _sanitize_number(self, value, default=0.0):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return float(default)
        if not math.isfinite(number):
            return float(default)
        return number

    def update_recoil(self, x, y):
        """Updates the recoil profile"""
        safe_x = self._sanitize_number(x, default=0.0)
        safe_y = self._sanitize_number(y, default=0.0)
        with self._state_lock:
            self.recoil_x = safe_x
            self.recoil_y = safe_y

    def set_multiplier(self, mult):
        """Sets the intensity smoothing multiplier"""
        safe_mult = self._sanitize_number(mult, default=0.5)
        safe_mult = max(0.01, min(1.0, safe_mult))
        with self._state_lock:
            self.multiplier = safe_mult

    def stop(self):
        """Stops the macro loop gracefully."""
        with self._state_lock:
            self.running = False


    def start(self):
        """Starts the main polling loop for mouse events."""
        with self._state_lock:
            self.running = True
        
        while True:
            with self._state_lock:
                if not self.running:
                    break
            try:
                # GetKeyState via ctypes ignores the thread message pump limitations
                caps_lock_on = ctypes.windll.user32.GetKeyState(win32con.VK_CAPITAL) & 0x0001
                with self._state_lock:
                    self.is_active = bool(caps_lock_on)
                    recoil_x = self.recoil_x
                    recoil_y = self.recoil_y
                    multiplier = self.multiplier

                if caps_lock_on:
                    # Check if Right Mouse Button is pressed (Aiming)
                    rmb_pressed = win32api.GetAsyncKeyState(win32con.VK_RBUTTON) < 0
                    
                    if rmb_pressed:
                        # Check if Left Mouse Button is pressed (Shooting)
                        lmb_pressed = win32api.GetAsyncKeyState(win32con.VK_LBUTTON) < 0
                        
                        if lmb_pressed:
                            # Original Lua logic: MoveMouseRelative(recoilX - 1, recoilY)
                            # We apply the multiplier to lessen aggressive pulling.
                            dx_target = (recoil_x - 1) * multiplier
                            dy_target = recoil_y * multiplier
                            
                            # Accumulate decimals to ensure smooth slow pull instead of jitter
                            self.accumulated_x += dx_target
                            self.accumulated_y += dy_target
                            
                            move_x = int(self.accumulated_x)
                            move_y = int(self.accumulated_y)
                            
                            # Only move mouse if there's actually a full pixel to move
                            if move_x != 0 or move_y != 0:
                                win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, move_x, move_y, 0, 0)
                                self.accumulated_x -= move_x
                                self.accumulated_y -= move_y
                            
                            # Random sleep between 2 and 3 ms as per Lua script: Sleep(math.random(2,3))
                            time.sleep(random.uniform(0.002, 0.003))
                            continue 
                            
                    # Reset accumulators if not actively firing
                    self.accumulated_x = 0.0
                    self.accumulated_y = 0.0
            except Exception as e:
                logger.exception("[Macro Error] Polling loop failure: %s", e)
                
            # Sleep 1ms to prevent 100% CPU utilization
            time.sleep(0.001)
