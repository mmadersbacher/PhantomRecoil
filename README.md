# Phantom Recoil

Phantom Recoil is a Windows desktop application (Python + PyWebView) for configuring recoil profiles with DPI-aware scaling.

## Scope
- Desktop UI for operator and weapon profile selection.
- Runtime recoil loop with Caps Lock activation guard.
- Persistent local preferences (DPI, favorites).
- Optional update notification based on GitHub releases.

## Security Model
- The updater does not download or execute binaries automatically.
- Update prompts open the official GitHub releases page only.
- Users should verify downloaded binaries with SHA256 checksums.

## Download Verification
Verify the release executable hash in PowerShell:

```powershell
Get-FileHash .\Phantom_Recoil_Standalone.exe -Algorithm SHA256
```

Compare the resulting hash with `SHA256SUMS.txt` from the same release.

## Run From Source
Requirements:
- Windows
- Python 3.9+

Run:

```bat
START.bat
```

`START.bat` installs required dependencies and launches `ui_app.py`.

## Build
Build distributable binaries:

```bat
BUILD.bat
```

Artifacts:
- `Phantom_Recoil.exe` (onedir runtime)
- `Phantom_Recoil_Standalone.exe` (onefile distribution)
- `SHA256SUMS.txt` (hash output)

`BUILD.bat` performs preflight validation and exits with explicit errors when prerequisites are missing.

## Launch Built Binary

```bat
PLAY.bat
```

`PLAY.bat` invokes `BUILD.bat` automatically if the standalone executable is not present and stops on build failures.

## Tests
Run all unit tests:

```bat
python -m unittest discover -s tests -p "test_*.py"
```

## Continuous Integration
The workflow in `.github/workflows/build.yml` performs:
1. Dependency installation
2. Unit test execution
3. Standalone executable build
4. SHA256 generation
5. Artifact upload (binary + checksum)

## Repository Structure
- `ui_app.py`: application entry point and PyWebView API bridge.
- `macro.py`: recoil runtime loop.
- `updater.py`: release check and user notification logic.
- `web/`: frontend assets (`index.html`, `script.js`, `style.css`, `data.js`).
- `tests/`: unit tests.
- `RELEASE_CHECKLIST.md`: release procedure for public publishing.
