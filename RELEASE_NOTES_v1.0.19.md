# Phantom Recoil v1.0.19

## Overview
This release updates the in-app operator and loadout data to match Ubisoft's current operator pages and synchronizes project version metadata.

## Highlights
- Synced `web/data.js` against official Rainbow Six Siege operator pages.
- Added missing operators and completed primary/secondary weapon coverage.
- Expanded local operator dataset from 71 to 77 operators.
- Expanded weapon entries from 104 to 307 entries.

## Data Notes
- Existing recoil values were preserved where already present.
- Shared weapon values were reused across operators when available.
- New weapons without prior local values were initialized with conservative defaults based on weapon class.

## Versioning
- Updated runtime updater version to `v1.0.19`.
- Updated installer default version to `1.0.19`.
- Updated CI `APP_VERSION` to `1.0.19`.

## Verification
- Unit tests: `22 passed`.
