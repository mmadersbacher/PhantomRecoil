# Release Checklist

## Versioning
1. Update `updater.py` (`__version__`) to the next `vX.Y.Z`.
2. Ensure Git tag format matches `vX.Y.Z`.

## Validation
1. Run unit tests:
   - `python -m unittest discover -s tests -p "test_*.py"`
2. Run build:
   - `BUILD.bat`
3. Build installer:
   - Inno Setup: `ISCC.exe installer.iss /DAppVersion=X.Y.Z`
3. Confirm artifacts exist:
   - `Phantom_Recoil_Standalone.exe`
   - `PhantomRecoilSetup_vX.Y.Z.exe`
   - `SHA256SUMS.txt`
   - `latest.json`
4. Smoke test executable startup:
   - Start EXE and ensure process launches without immediate crash.
5. Smoke test installer:
   - Install, launch, and uninstall without errors.

## Release Publishing
1. Create a GitHub Release for the matching tag.
2. Upload:
   - `PhantomRecoilSetup_vX.Y.Z.exe`
   - `Phantom_Recoil_Standalone.exe`
   - `SHA256SUMS.txt`
   - `latest.json`
3. In release notes, include:
   - SHA256 verification instruction
   - security note: download only from official repository releases
   - signer identity when code signing is enabled

## Code Signing and Authenticity
1. Sign installer and executable with Authenticode in the secure release environment.
2. Timestamp signatures using a trusted timestamp service.
3. Verify signatures before publishing:
   - `Get-AuthenticodeSignature .\PhantomRecoilSetup_vX.Y.Z.exe`
   - `Get-AuthenticodeSignature .\Phantom_Recoil_Standalone.exe`
4. Publish only if signature status is `Valid`.
5. For immediate SmartScreen trust on fresh downloads, use an EV code-signing certificate.
6. Keep the publisher identity stable across releases (same legal entity name and certificate chain).
7. Optional helper script for manual release signing:
   - `SIGN_RELEASE.bat X.Y.Z`

## Post-Release Check
1. Install/download from the public release as a fresh user.
2. Verify checksum with PowerShell:
   - `Get-FileHash .\PhantomRecoilSetup_vX.Y.Z.exe -Algorithm SHA256`
   - `Get-FileHash .\Phantom_Recoil_Standalone.exe -Algorithm SHA256`
3. Confirm updater applies update automatically on startup (no browser redirect).
