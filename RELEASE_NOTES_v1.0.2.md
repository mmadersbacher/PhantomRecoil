# Phantom Recoil v1.0.2

## Overview
This release focuses on security hardening, runtime stability, build reproducibility, and public distribution readiness.

## Highlights
- Hardened runtime state handling in the recoil loop.
- Added strict backend input validation and graceful shutdown behavior.
- Refactored frontend event handling to remove unsafe inline patterns.
- Improved build and release pipeline with preflight checks and checksum generation.
- Added CI workflow for automated tests, build, and artifact publishing.
- Reworked documentation for professional public release use.

## Security Improvements
- Removed inline `onclick` usage in frontend code and replaced it with safe event listeners.
- Removed unsafe dynamic HTML injection paths in critical UI rendering.
- Added client and backend numeric validation for recoil and multiplier values.
- Improved updater error handling (network, JSON parsing, HTTP status, rate limiting).
- Updater behavior remains non-destructive: no automatic binary download or execution.

## Reliability and Stability
- Added thread-safe state access in `macro.py`.
- Added robust application shutdown flow in `ui_app.py`.
- Added defensive startup checks for required UI resources.
- Added empty-state and responsive handling improvements in the web UI.

## Build and Release Pipeline
- `BUILD.bat` now performs preflight validation and strict error handling.
- Build output integrity checks added.
- `SHA256SUMS.txt` is generated automatically during build.
- `PLAY.bat` now aborts cleanly if build fails.
- GitHub Actions workflow now runs tests, builds the executable, and publishes binary + checksum artifacts.

## Testing
- Added and validated unit tests for:
  - updater version parsing and comparison logic
  - macro numeric sanitization and multiplier clamping
  - API numeric finite-value conversion
- Local test execution result: `8 passed`.

## Verification
SHA256 (`Phantom_Recoil_Standalone.exe`):

```text
DA5FEA3E6DE89B4BB0BD044E54DCBA990898DBD803D178DF58D62FB4DFADD71C
```

Verification command:

```powershell
Get-FileHash .\Phantom_Recoil_Standalone.exe -Algorithm SHA256
```

## Notes for Maintainers
- Release tag format should be `vX.Y.Z`.
- Keep `updater.py::__version__` aligned with the published release tag.
- Publish both `Phantom_Recoil_Standalone.exe` and `SHA256SUMS.txt` in GitHub Releases.
