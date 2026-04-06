# Phantom Recoil v1.0.41

## Overview
Rapid fire flow fix and timing optimization for smoother, faster burst firing.

## Rapid Fire Improvements
- Fixed critical fall-through bug in the main macro loop: after each rapid-fire shot the code incorrectly fell into the burst-reset path, causing a redundant `LEFTUP` event before every shot and an extra 2 ms overhead per cycle.
- The `_rf_hold_neutralized` flag is now preserved across the entire burst — `_rf_prime_burst` neutralizes the physical hold exactly once at burst start, not once per shot.
- Result: the injected click sequence is now a clean `LEFTUP → DOWN → UP → DOWN → UP → …` instead of `LEFTUP → DOWN → UP → LEFTUP → DOWN → UP → …` which was causing visible stutter in the firing animation.
- Tightened click-hold distribution: mode 38 ms (was 42 ms), range 26–68 ms (was 28–75 ms).
- Tightened inter-shot gap distribution: mode 55 ms (was 62 ms), range 40–85 ms (was 45–95 ms).
- Net result: ~10.8 shots/sec at mode (was ~9.5), still well within human-plausible range. All anti-cheat simulations (micro-tremor, fatigue, fumble, triangular distributions) remain fully intact.

## Tests
- Updated `TestRapidFire` suite to match the current `_rf_fire_shot` signature (removed stale `now` parameter and `_rf_next_shot_at` references from a prior iteration).
- Replaced `test_rf_fire_shot_skips_before_interval` (concept removed) with `test_rf_fire_shot_down_before_up` (order guarantee) and `test_rf_fire_shot_releases_on_exception` (exception safety).
- All 43 tests pass.

## Version Sync
- Runtime updater version: `v1.0.41`
- `latest.json` updated to `v1.0.41`
