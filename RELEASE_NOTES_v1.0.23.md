# Phantom Recoil v1.0.23

## Overview
This release finalizes the fully free update channel using GitHub Releases + `latest.json` manifest and improves installer behavior for non-admin users.

## Update Flow Improvements
- Updater now prefers `latest.json` from the latest GitHub release:
  - `https://github.com/mmadersbacher/PhantomRecoil/releases/latest/download/latest.json`
- Falls back to GitHub Releases API if manifest is missing/invalid.
- Supports inline SHA256 checks directly from manifest asset metadata.
- Keeps checksum verification via `SHA256SUMS.txt` as fallback.

## Packaging / Install
- Installer default path changed to per-user:
  - `%LOCALAPPDATA%\\Programs\\Phantom Recoil`
- This aligns with `PrivilegesRequired=lowest` and avoids Program Files write issues for auto-update.

## Release Tooling
- Added `generate_latest_manifest.py` to generate `latest.json`.
- CI now generates and publishes `latest.json` as build artifact.
- Updated release checklist and docs to include `latest.json`.

## Version Sync
- Runtime updater version: `v1.0.23`
- Installer default version: `1.0.23`
- CI `APP_VERSION`: `1.0.23`
