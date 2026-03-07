<p align="center">
	<img src="docs/assets/phantom-recoil-logo.svg" alt="Phantom Recoil Logo Banner" width="100%" />
</p>

<p align="center">
	<a href="https://github.com/mmadersbacher/PhantomRecoil/releases"><img src="https://img.shields.io/github/v/release/mmadersbacher/PhantomRecoil?style=for-the-badge&label=release" alt="Latest Release" /></a>
	<a href="https://github.com/mmadersbacher/PhantomRecoil/actions/workflows/build.yml"><img src="https://img.shields.io/github/actions/workflow/status/mmadersbacher/PhantomRecoil/build.yml?style=for-the-badge&label=build" alt="Build Status" /></a>
	<a href="https://github.com/mmadersbacher/PhantomRecoil/stargazers"><img src="https://img.shields.io/github/stars/mmadersbacher/PhantomRecoil?style=for-the-badge" alt="GitHub Stars" /></a>
	<a href="https://github.com/mmadersbacher/PhantomRecoil/issues"><img src="https://img.shields.io/github/issues/mmadersbacher/PhantomRecoil?style=for-the-badge" alt="Open Issues" /></a>
</p>

# Phantom Recoil

**Phantom Recoil** is a modern Windows desktop recoil profile manager for Rainbow Six Siege, designed with an enterprise-grade UI, smooth interaction flow, strong diagnostics, reproducible builds, and release-ready packaging.

This project combines **Python + PyWebView + modern web UI** to deliver a lightweight but professional desktop tool with persistent settings, per-weapon recoil intensity, DPI scaling, icon caching, and robust update/release workflows.

## Why This Project Exists

Most recoil helpers are either throwaway scripts or hard to maintain long-term. Phantom Recoil focuses on the opposite:

- Consistent UX and polished visual design.
- Real release engineering (installer + portable + checksums + CI).
- Stability hardening and diagnostics for fast issue triage.
- Maintainable code structure suitable for active development.

## Core Feature Highlights

- Fast operator + weapon selection.
- Live recoil profile handoff to backend macro loop.
- DPI-aware recoil scaling for different mouse setups.
- Per-weapon intensity persistence.
- Favorites and search for quick access.
- Icon fetching with local cache fallback behavior.
- Stable tab switching and preserved scroll behavior on selection.
- Built-in update checks against official releases.
- Installer + portable release assets.

## SEO Section

This section is intentionally optimized with relevant phrases so developers and end users can discover the repository more easily.

### Primary SEO Keywords

- rainbow six siege recoil manager
- r6 recoil profile desktop app
- windows recoil control utility
- pywebview desktop app python
- recoil pattern profile selector
- recoil intensity per weapon storage
- dpi recoil scaling utility
- windows installer pyinstaller inno setup

### Long-Tail SEO Phrases

- enterprise style rainbow six recoil manager for windows
- python recoil desktop tool with per weapon intensity memory
- pywebview recoil app with diagnostics and updater
- recoil profile manager with favorites and search
- inno setup installer fix deletefile failed code 5
- modern dark enterprise desktop ui with cached icons

### SEO Description Snippet

Use this for release pages, social cards, or listings:

`Phantom Recoil is a professional Windows recoil profile manager for Rainbow Six Siege with DPI scaling, per-weapon intensity memory, icon caching, diagnostics, and polished enterprise-grade UI.`

## Technology Stack

| Area | Technology | Purpose |
|---|---|---|
| Core Runtime | Python | Application logic and backend APIs |
| Desktop Shell | PyWebView | Native app window + JS bridge |
| Frontend | HTML + CSS + JavaScript | UI rendering and interactions |
| Build System | PyInstaller | Standalone executable packaging |
| Installer | Inno Setup | Windows installation flow |
| CI/CD | GitHub Actions | Build, test, package, release artifacts |
| Integrity | SHA256 | Download verification |

## Architecture Overview

```text
UI Layer (web/index.html + web/style.css + web/script.js)
		|
		| window.pywebview.api.*
		v
App Bridge (ui_app.py)
		|
		+--> Macro Runtime (macro.py)
		+--> Updater (updater.py)
		+--> Diagnostic Watchdog + Logging

Release Layer
		+--> PyInstaller builds EXE(s)
		+--> Inno Setup creates installer
		+--> SHA256SUMS generated for integrity
```

## Repository Tree

```text
PhantomRecoil/
|-- BUILD.bat
|-- START.bat
|-- PLAY.bat
|-- SIGN_RELEASE.bat
|-- installer.iss
|-- ui_app.py
|-- macro.py
|-- updater.py
|-- README.md
|-- RELEASE_CHECKLIST.md
|-- web/
|   |-- index.html
|   |-- style.css
|   |-- script.js
|   `-- data.js
|-- tests/
|   |-- test_macro.py
|   |-- test_ui_api.py
|   `-- test_updater.py
|-- docs/
|   `-- assets/
|       `-- phantom-recoil-logo.svg
`-- .github/workflows/build.yml
```

## Download and Installation

### Recommended Path (Installer)

1. Open official releases:
	 - `https://github.com/mmadersbacher/PhantomRecoil/releases`
2. Download latest setup:
	 - `PhantomRecoilSetup_vX.Y.Z.exe`
3. Run installer and complete setup.
4. Launch from Start Menu: `Phantom Recoil`.

### Portable Path (No Installation)

Download:
- `Phantom_Recoil_Standalone.exe`

Then run directly.

## SmartScreen and Trust Notes

- Windows SmartScreen can warn on unsigned binaries.
- Always download only from the official release page.
- Verify checksums before running executables.
- If signature is present, verify Authenticode status.

## Integrity Verification

Download `SHA256SUMS.txt` from the same release and verify:

```powershell
Get-FileHash .\PhantomRecoilSetup_vX.Y.Z.exe -Algorithm SHA256
Get-FileHash .\Phantom_Recoil_Standalone.exe -Algorithm SHA256
```

Hashes must match `SHA256SUMS.txt`.

If signing is enabled:

```powershell
Get-AuthenticodeSignature .\PhantomRecoilSetup_vX.Y.Z.exe
Get-AuthenticodeSignature .\Phantom_Recoil_Standalone.exe
```

Expected status: `Valid`.

## Usage Guide

1. Choose category tab (`Attackers`, `Defenders`, `Favorites`).
2. Search operator or weapon when needed.
3. Select your weapon profile.
4. Adjust DPI and intensity.
5. App stores intensity per selected weapon automatically.

### Persistence Model

- Favorites are stored locally.
- DPI is stored locally.
- Recoil intensity is stored per weapon.
- UI caches icon responses for smoother repeated browsing.

## Build from Source

### Requirements

- Windows
- Python 3.9+

### Run Development Launcher

```bat
START.bat
```

### Build Release Artifacts

```bat
BUILD.bat
```

Expected outputs:
- `Phantom_Recoil.exe`
- `Phantom_Recoil_Standalone.exe`
- `PhantomRecoilSetup_vX.Y.Z.exe`
- `SHA256SUMS.txt`

### Run Built App

```bat
PLAY.bat
```

### Run Tests

```bat
python -m unittest discover -s tests -p "test_*.py"
```

## CI/CD Pipeline

Workflow: `.github/workflows/build.yml`

Pipeline stages:
1. Checkout and Python setup
2. Dependency installation
3. Unit test execution
4. Standalone build
5. Installer build
6. SHA256 generation
7. Artifact publishing

## Signing Helper (Optional)

Local helper script:

```bat
set SIGN_PFX_FILE=C:\secure\codesign.pfx
set SIGN_PFX_PASSWORD=YOUR_SECRET
SIGN_RELEASE.bat X.Y.Z
```

## Troubleshooting

### Installer Cannot Replace Existing File

- Close all running Phantom Recoil processes.
- Retry installer once.
- Use latest release (installer includes stronger process-close logic).

### SmartScreen Warning Appears

- Validate release URL + checksums.
- Continue only when artifacts are from official releases.

### App Becomes Unresponsive

- Reproduce once on latest version.
- Share diagnostic log:
	- `%LOCALAPPDATA%\PhantomRecoil\logs\phantom_recoil_diagnostic.log`

## Roadmap

- Scope-specific multipliers.
- Preset import/export profiles.
- Local icon pack fallback mode.
- Expanded analytics for debug builds.
- Optional plugin-style profile packs.

## Contributing

Contributions are welcome.

Suggested workflow:
1. Fork repository.
2. Create feature branch.
3. Keep changes focused and test-backed.
4. Open PR with clear summary and validation steps.

## Support the Project

If Phantom Recoil helps you, star the repository so more users can discover it.

