# Phantom Recoil v1.0.40

## Overview
This release combines a full rapid-fire stabilization pass with a substantial desktop UI polish pass.

## Rapid Fire Fixes
- Reworked the rapid-fire click flow so every synthetic burst ends in a guaranteed `LEFTUP`.
- Added physical left-click tracking that ignores the app's own injected mouse events.
- Hardened reset paths when rapid fire is disabled, interrupted, or the macro exits.
- Added regression coverage for the rapid-fire timing and reset edge cases.

## UI Polish
- Rebuilt the sidebar header and control layout for a cleaner, more release-ready presentation.
- Fixed operator badge rendering so logos sit properly in their containers instead of looking stretched or awkwardly cropped.
- Improved card spacing, visual hierarchy, and weapon row readability across the main grid.
- Reduced noisy decorative patterns and moved warning messaging into a less intrusive overlay.

## Version Sync
- Runtime updater version: `v1.0.40`
- Installer default version: `1.0.40`
- CI `APP_VERSION`: `1.0.40`

## Verification
- Unit tests: `43 passed`.
