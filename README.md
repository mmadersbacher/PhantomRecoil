# Phantom Recoil

Phantom Recoil is a Windows desktop application for recoil profile selection with DPI-aware scaling.

## Download and Install (Recommended)
1. Open the official releases page:
	- `https://github.com/mmadersbacher/RainbowSixRecoil/releases`
2. Download the latest installer:
	- `PhantomRecoilSetup_vX.Y.Z.exe`
3. Run the installer.
4. Start the app from Start Menu: `Phantom Recoil`.

If Windows SmartScreen appears, verify that you downloaded the file from the official GitHub repository above.

## Alternative: Portable EXE
If you do not want to install, download:
- `Phantom_Recoil_Standalone.exe`

Then run the file directly.

## Verify Download Integrity (Important)
Download `SHA256SUMS.txt` from the same release and verify in PowerShell:

```powershell
Get-FileHash .\PhantomRecoilSetup_vX.Y.Z.exe -Algorithm SHA256
Get-FileHash .\Phantom_Recoil_Standalone.exe -Algorithm SHA256
```

The hash values must match `SHA256SUMS.txt`.

If code signing is enabled for a release, verify signer status:

```powershell
Get-AuthenticodeSignature .\PhantomRecoilSetup_vX.Y.Z.exe
```

Expected: `Status = Valid`.

## Features
- Operator and weapon profile UI.
- DPI scaling support.
- Saved local settings (DPI, favorites).
- Optional update notifications via GitHub release checks.

## For Developers

### Run From Source
Requirements:
- Windows
- Python 3.9+

Run:

```bat
START.bat
```

`START.bat` installs required dependencies and launches `ui_app.py`.

### Build
Build distributable binaries:

```bat
BUILD.bat
```

Artifacts:
- `Phantom_Recoil.exe` (onedir runtime)
- `Phantom_Recoil_Standalone.exe` (onefile distribution)
- `PhantomRecoilSetup_vX.Y.Z.exe` (Inno Setup installer)
- `SHA256SUMS.txt` (hash output)

`BUILD.bat` performs preflight validation and exits with explicit errors when prerequisites are missing.

### Launch Built Binary

```bat
PLAY.bat
```

`PLAY.bat` invokes `BUILD.bat` automatically if the standalone executable is not present and stops on build failures.

### Tests
Run all unit tests:

```bat
python -m unittest discover -s tests -p "test_*.py"
```

### Continuous Integration
The workflow in `.github/workflows/build.yml` performs:
1. Dependency installation
2. Unit test execution
3. Standalone executable build
4. Installer build (Inno Setup)
5. SHA256 generation for executable and installer
6. Artifact upload (executable, installer, checksum)

### Repository Structure
- `ui_app.py`: application entry point and PyWebView API bridge.
- `macro.py`: recoil runtime loop.
- `updater.py`: release check and user notification logic.
- `web/`: frontend assets (`index.html`, `script.js`, `style.css`, `data.js`).
- `tests/`: unit tests.
- `installer.iss`: installer definition for Inno Setup.
- `RELEASE_CHECKLIST.md`: release procedure for public publishing.
