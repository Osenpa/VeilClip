# Releasing VeilClip

This project ships two Windows release assets:

- installer: `VeilClip-Setup-<version>.exe`
- portable EXE ZIP: `VeilClip-Portable-<version>.zip`

## Build Command

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_installer.ps1
```

## Expected Outputs

After a successful build:

- `dist-installer/` contains the installer `.exe` and sidecar release note
- `dist-portable/` contains the portable `.zip` and optional sidecar release note
- the portable ZIP contains a single folder with `VeilClip.exe`, bundled runtime files, `RELEASE.txt`, and `LICENSE.txt`

## Release Sources

- combined release-page body: `releases/<version>/CODEBERG_RELEASE.md`
- installer note template: `releases/<version>/INSTALLER_RELEASE.txt`
- portable note template: `releases/<version>/PORTABLE_RELEASE.txt`

## Pre-Release Checks

- verify `utils/config.py` version matches the intended release
- rebuild both assets from a clean working tree
- confirm `README.md`, `CHANGELOG.md`, `LICENSE`, `SECURITY.md`, and `SUPPORT.md` are current
- test installer install, launch, uninstall, and startup shortcut behavior
- test portable ZIP extraction and first launch
- verify website, app page, donate, email, and Codeberg links
- verify the portable ZIP includes `RELEASE.txt` and `LICENSE.txt`
