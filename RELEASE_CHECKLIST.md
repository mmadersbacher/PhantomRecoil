# Release Checklist

## Versioning
1. Update `updater.py` (`__version__`) to the next `vX.Y.Z`.
2. Ensure Git tag format matches `vX.Y.Z`.

## Validation
1. Run unit tests:
   - `python -m unittest discover -s tests -p "test_*.py"`
2. Run build:
   - `BUILD.bat`
3. Confirm artifacts exist:
   - `Phantom_Recoil_Standalone.exe`
   - `SHA256SUMS.txt`
4. Smoke test executable startup:
   - Start EXE and ensure process launches without immediate crash.

## Release Publishing
1. Create a GitHub Release for the matching tag.
2. Upload:
   - `Phantom_Recoil_Standalone.exe`
   - `SHA256SUMS.txt`
3. In release notes, include:
   - SHA256 verification instruction
   - security note: download only from official repository releases

## Post-Release Check
1. Install/download from the public release as a fresh user.
2. Verify checksum with PowerShell:
   - `Get-FileHash .\Phantom_Recoil_Standalone.exe -Algorithm SHA256`
3. Confirm updater notification opens official release page only.
