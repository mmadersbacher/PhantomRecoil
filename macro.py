import time
import win32api
import win32con
import random
import threading
import ctypes

class RecoilMacro:
    def __init__(self):
        self.recoil_x = 0
        self.recoil_y = 0
        self.multiplier = 0.5
        self.running = False
        
        # Accumulators allow for sub-pixel smooth movements
        # when intensity multiplier creates float values
        self.accumulated_x = 0.0
        self.accumulated_y = 0.0
        self.is_active = False

    def update_recoil(self, x, y):
        """Updates the recoil profile"""
        self.recoil_x = x
        self.recoil_y = y

    def set_multiplier(self, mult):
        """Sets the intensity smoothing multiplier"""
        self.multiplier = mult

    def stop(self):
        """Stops the macro loop gracefully."""
        self.running = False


    def start(self):
        """Starts the main polling loop for mouse events."""
        self.running = True
        
        while self.running:
            try:
                # GetKeyState via ctypes ignores the thread message pump limitations
                caps_lock_on = ctypes.windll.user32.GetKeyState(win32con.VK_CAPITAL) & 0x0001
                self.is_active = caps_lock_on

                if caps_lock_on:
                    # Check if Right Mouse Button is pressed (Aiming)
                    rmb_pressed = win32api.GetAsyncKeyState(win32con.VK_RBUTTON) < 0
                    
                    if rmb_pressed:
                        # Check if Left Mouse Button is pressed (Shooting)
                        lmb_pressed = win32api.GetAsyncKeyState(win32con.VK_LBUTTON) < 0
                        
                        if lmb_pressed:
                            # Original Lua logic: MoveMouseRelative(recoilX - 1, recoilY)
                            # We apply the multiplier to lessen aggressive pulling.
                            dx_target = (self.recoil_x - 1) * self.multiplier
                            dy_target = self.recoil_y * self.multiplier
                            
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
                print(f"[Macro Error] {e}")
                
            # Sleep 1ms to prevent 100% CPU utilization
            time.sleep(0.001)
