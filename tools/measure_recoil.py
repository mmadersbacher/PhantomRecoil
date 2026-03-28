"""
R6S Recoil Pattern Analyzer
============================
Measures per-shot recoil for each weapon by analyzing live screen capture.

How it works:
  1. Calibration: injects a known mouse movement via SendInput, measures how
     many pixels the view shifts → derives px_per_unit for current settings.
  2. Recording: captures the screen at ~60 fps while you fire full-auto.
  3. Shot detection: finds muzzle-flash frames via a brightness spike in the
     lower-center region of the screen.
  4. Optical flow: tracks wall-texture features between consecutive shot frames
     with Lucas-Kanade. The background moves opposite to the recoil direction.
  5. Output: prints weapon.x / weapon.y values ready for data.js, and saves a
     JSON file with the full per-shot pattern.

Requirements:
    pip install opencv-python mss numpy pywin32

IMPORTANT – record at REFERENCE settings so values drop straight into data.js:
    DPI: 400   |   In-Game Sensitivity: 50   |   ADS Sens: 100%   |   H/V: 100
"""

import ctypes
import json
import sys
import time
from pathlib import Path

import cv2
import mss
import numpy as np
import win32api
import win32con


# ── Tunable constants ─────────────────────────────────────────────────────────

CAPTURE_FPS        = 60      # Target capture rate
MONITOR_INDEX      = 1       # 1 = primary monitor

# Muzzle-flash ROI as fractions of screen (left, right, top, bottom)
# This covers the lower-center area where gun model + flash appear.
FLASH_ROI          = (0.35, 0.65, 0.55, 0.85)
FLASH_THRESHOLD    = 20      # Minimum brightness delta to count as a shot
FLASH_MIN_GAP      = 3       # Minimum frames between two detected shots

# How many mouse units to inject during calibration
CALIB_UNITS        = 600

# Hotkey to start / stop recording
HOTKEY_VK          = win32con.VK_F9

# Reference settings (values the recoil profiles are calibrated against)
REFERENCE_DPI      = 400
REFERENCE_SENS     = 50

# Average macro tick duration in ms (macro sleeps 2–3 ms, mean ≈ 2.5 ms)
TICK_MS            = 2.5


# ── SendInput helpers ─────────────────────────────────────────────────────────

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
    _fields_ = [('type', ctypes.c_ulong), ('_input', _INPUT_UNION)]

def _inject_mouse(dx: int, dy: int) -> None:
    inp = _INPUT(type=0)
    inp._input.mi = _MOUSEINPUT(
        dx=dx, dy=dy, mouseData=0, dwFlags=0x0001, time=0,
        dwExtraInfo=ctypes.pointer(ctypes.c_ulong(0)),
    )
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


# ── Calibration ───────────────────────────────────────────────────────────────

def calibrate(sct, monitor) -> tuple[float, float]:
    """
    Inject CALIB_UNITS mouse counts horizontally, measure the resulting
    pixel shift via optical flow, return (px_per_unit_x, px_per_unit_y).

    Must be called while R6S is in focus and the player is ADS at a wall,
    so the injected movement registers in-game at the correct ADS sensitivity.
    """
    h, w = monitor['height'], monitor['width']
    cy, cx = h // 2, w // 2

    # Mask out the center scope area for feature detection
    scope_mask = np.ones((h, w), dtype=np.uint8) * 255
    scope_mask[cy - h//4 : cy + h//4, cx - w//4 : cx + w//4] = 0

    frame_before = np.array(sct.grab(monitor))[:, :, :3]
    time.sleep(0.04)

    _inject_mouse(CALIB_UNITS, 0)
    time.sleep(0.12)

    frame_after = np.array(sct.grab(monitor))[:, :, :3]

    # Restore position
    _inject_mouse(-CALIB_UNITS, 0)
    time.sleep(0.12)

    dx_px, dy_px = _optical_flow(frame_before, frame_after, scope_mask)

    if abs(dx_px) < 1.0:
        print("  WARNING: Calibration shift too small – is R6S focused and in ADS? Using fallback 1.0.")
        return 1.0, 1.0

    px_per_unit_x = dx_px / CALIB_UNITS
    # dy_px should be near 0 for a horizontal injection; keep y conversion symmetric
    px_per_unit_y = abs(px_per_unit_x)

    print(f"  Injected {CALIB_UNITS} units → {dx_px:.1f} px horizontal")
    print(f"  Conversion: {px_per_unit_x:.5f} px/unit")
    return px_per_unit_x, px_per_unit_y


# ── Shot detection ────────────────────────────────────────────────────────────

def detect_shots(frames: list, h: int, w: int) -> list[int]:
    """
    Return frame indices where a muzzle flash is detected.
    Strategy: track mean brightness in the lower-center ROI and flag sudden spikes.
    """
    y1, y2 = int(h * FLASH_ROI[2]), int(h * FLASH_ROI[3])
    x1, x2 = int(w * FLASH_ROI[0]), int(w * FLASH_ROI[1])

    brightness = [float(np.mean(f[y1:y2, x1:x2])) for f in frames]

    shots = []
    for i in range(1, len(brightness)):
        delta = brightness[i] - brightness[i - 1]
        if delta > FLASH_THRESHOLD:
            if not shots or i - shots[-1] >= FLASH_MIN_GAP:
                shots.append(i)

    return shots


# ── Optical flow ──────────────────────────────────────────────────────────────

def _optical_flow(frame1: np.ndarray, frame2: np.ndarray,
                  mask: np.ndarray | None = None) -> tuple[float, float]:
    """
    Lucas-Kanade sparse optical flow.
    Returns median (dx, dy) of tracked background points.
    dx/dy > 0 means features moved RIGHT/DOWN, so recoil is LEFT/UP (negate for recoil).
    """
    h, w = frame1.shape[:2]

    if mask is None:
        cy, cx = h // 2, w // 2
        mask = np.ones((h, w), dtype=np.uint8) * 255
        mask[cy - h//4 : cy + h//4, cx - w//4 : cx + w//4] = 0

    g1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)

    pts = cv2.goodFeaturesToTrack(g1, maxCorners=300, qualityLevel=0.005,
                                   minDistance=10, mask=mask)
    if pts is None or len(pts) < 5:
        return 0.0, 0.0

    pts2, status, _ = cv2.calcOpticalFlowPyrLK(g1, g2, pts, None,
                                                winSize=(21, 21), maxLevel=3)
    ok = status.ravel() == 1
    if ok.sum() < 3:
        return 0.0, 0.0

    dx = float(np.median(pts2[ok][:, 0, 0] - pts[ok][:, 0, 0]))
    dy = float(np.median(pts2[ok][:, 0, 1] - pts[ok][:, 0, 1]))
    return dx, dy


# ── Main capture & analysis ───────────────────────────────────────────────────

def run(weapon: str, dpi: int, sensitivity: int, rpm: int | None) -> None:
    print(f"\n{'='*55}")
    print(f"  Weapon : {weapon}")
    print(f"  DPI    : {dpi}   Sensitivity : {sensitivity}")
    print(f"  RPM    : {rpm or 'auto-detect via flash timing'}")
    print(f"{'='*55}\n")

    with mss.mss() as sct:
        monitor = sct.monitors[MONITOR_INDEX]
        h, w = monitor['height'], monitor['width']

        # ── Calibration ────────────────────────────────────────────────
        print("Step 1/3 – Calibration")
        print("  • Go to R6S Shooting Range, select weapon, ADS at the plain wall.")
        print("  • Make sure R6S window is in FOCUS.")
        input("  Press ENTER when ready… ")
        print("  Calibrating (your view will briefly shift right then snap back)…")
        px_per_unit_x, px_per_unit_y = calibrate(sct, monitor)
        print("  Calibration done.\n")

        # ── Recording ──────────────────────────────────────────────────
        print("Step 2/3 – Recording")
        print(f"  • Stay ADS at the wall.")
        print(f"  • Press F9 to START, fire a FULL MAGAZINE, press F9 to STOP.")
        input("  Press ENTER when ready… ")

        while not (win32api.GetAsyncKeyState(HOTKEY_VK) & 0x8000):
            time.sleep(0.01)
        time.sleep(0.15)

        frames: list[np.ndarray] = []
        interval = 1.0 / CAPTURE_FPS
        print("  ● Recording… press F9 to stop")

        while True:
            t0 = time.perf_counter()
            frames.append(np.array(sct.grab(monitor))[:, :, :3])
            if win32api.GetAsyncKeyState(HOTKEY_VK) & 0x8000:
                break
            elapsed = time.perf_counter() - t0
            remaining = interval - elapsed
            if remaining > 0.001:
                time.sleep(remaining)

        print(f"  ■ Stopped. Captured {len(frames)} frames.\n")

        # ── Analysis ───────────────────────────────────────────────────
        print("Step 3/3 – Analysis")

        shots = detect_shots(frames, h, w)
        print(f"  Detected {len(shots)} shots at frames: {shots[:20]}")

        if len(shots) < 2:
            print("\n  ERROR: Too few shots detected.")
            print("  Try: lower FLASH_THRESHOLD, fire closer to the wall, or check the ROI.")
            return

        # Estimate RPM from flash timing if not provided
        if rpm is None:
            actual_fps = CAPTURE_FPS  # approximate
            inter_frame_gaps = [shots[i+1] - shots[i] for i in range(len(shots)-1)]
            avg_gap_frames = float(np.median(inter_frame_gaps))
            avg_gap_ms = avg_gap_frames / actual_fps * 1000
            estimated_rpm = int(60000 / avg_gap_ms)
            print(f"  Auto-detected RPM: {estimated_rpm}  (avg inter-shot gap: {avg_gap_ms:.1f} ms)")
            rpm_used = estimated_rpm
        else:
            rpm_used = rpm

        ticks_per_shot = (60000 / rpm_used) / TICK_MS

        # Scale factor to convert from recording settings to reference settings
        ref_scale = (REFERENCE_DPI / dpi) * (REFERENCE_SENS / sensitivity)

        # Scope mask for flow measurement
        cy, cx = h // 2, w // 2
        scope_mask = np.ones((h, w), dtype=np.uint8) * 255
        scope_mask[cy - h//4 : cy + h//4, cx - w//4 : cx + w//4] = 0

        pattern = []
        print(f"\n  {'Shot':>4}  {'dx_px':>8}  {'dy_px':>8}  {'x (data)':>10}  {'y (data)':>10}")
        print(f"  {'-'*48}")

        for i in range(len(shots) - 1):
            f1 = frames[shots[i]]
            f2 = frames[shots[i + 1]]
            dx_bg, dy_bg = _optical_flow(f1, f2, scope_mask)

            # Background moves opposite to view; recoil = view kick = -background motion
            dx_px = -dx_bg
            dy_px = -dy_bg

            # pixels → mouse units (using calibration)
            dx_units = dx_px / px_per_unit_x if px_per_unit_x != 0 else 0.0
            dy_units = dy_px / px_per_unit_y if px_per_unit_y != 0 else 0.0

            # Scale to reference settings
            dx_units *= ref_scale
            dy_units *= ref_scale

            # Convert total-per-shot displacement to per-tick value (weapon.y format)
            weapon_x_raw = dx_units / ticks_per_shot
            weapon_y_raw = dy_units / ticks_per_shot

            # data.js convention: x=1 is neutral horizontal (macro applies x-1 per tick)
            data_x = weapon_x_raw + 1.0
            data_y = weapon_y_raw

            pattern.append({"x": round(data_x, 2), "y": round(data_y, 2)})
            print(f"  {i+1:>4}  {dx_px:>+8.1f}  {dy_px:>+8.1f}  {data_x:>10.2f}  {data_y:>10.2f}")

        # Summary
        avg_x = float(np.mean([p['x'] for p in pattern]))
        avg_y = float(np.mean([p['y'] for p in pattern]))

        print(f"\n  Average (all shots):  x = {avg_x:.2f},  y = {avg_y:.2f}")
        print(f"\n  ▶ data.js entry (static average):")
        print(f'    {{ name: "{weapon}", x: {round(avg_x)}, y: {round(avg_y)} }}')

        # Save JSON
        output = {
            "weapon": weapon,
            "recording": {"dpi": dpi, "sensitivity": sensitivity, "rpm": rpm_used},
            "calibration": {"px_per_unit_x": px_per_unit_x, "px_per_unit_y": px_per_unit_y},
            "ticks_per_shot": round(ticks_per_shot, 1),
            "pattern": pattern,
            "summary": {"x": round(avg_x, 2), "y": round(avg_y, 2)},
            "data_js_static": {"name": weapon, "x": round(avg_x), "y": round(avg_y)},
        }

        out_path = Path(__file__).parent / f"recoil_{weapon.replace(' ', '_').lower()}.json"
        out_path.write_text(json.dumps(output, indent=2))
        print(f"\n  Full pattern saved → {out_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    print("╔══════════════════════════════════════════════════════╗")
    print("║       R6S Recoil Pattern Analyzer  v1.0             ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()
    print("IMPORTANT – use these settings in R6S during measurement:")
    print("  DPI: 400  |  In-Game Sensitivity: 50  |  ADS: 100%  |  H/V: 100")
    print("  (These are the reference values. Tool will auto-scale for other settings.)")
    print()

    weapon    = input("Weapon name (e.g. AK-12): ").strip() or "Unknown"
    dpi_s     = input("DPI used during recording [400]: ").strip()
    sens_s    = input("In-Game Sensitivity used [50]: ").strip()
    rpm_s     = input("Weapon RPM (leave blank to auto-detect from flash timing): ").strip()

    dpi  = int(dpi_s)  if dpi_s  else 400
    sens = int(sens_s) if sens_s else 50
    rpm  = int(rpm_s)  if rpm_s  else None

    run(weapon, dpi, sens, rpm)


if __name__ == "__main__":
    main()
