# VeilClip 1.0.0

VeilClip 1.0.0 is the first public open-source release of the offline clipboard manager for Windows.

## Downloads

- `VeilClip-Setup-1.0.0.exe`: installer build for standard Windows setup
- `VeilClip-Portable-1.0.0.zip`: portable EXE ZIP for no-install use

## Highlights

- local clipboard history for text, links, images, and file paths
- Favorites with categories and drag-and-drop reuse
- encrypted Locked Notes protected by a PIN
- text editing, image editing, and plain-text copy tools
- local backup, JSON export, and CSV export/import support
- multi-language UI with 16 bundled languages
- offline-first design with no cloud requirement

## Choose the Right Package

Installer:

- guided setup wizard
- Start Menu and desktop shortcut support
- startup shortcut support
- standard uninstall flow

Portable EXE ZIP:

- extract anywhere and run `VeilClip.exe`
- no installer required
- includes `RELEASE.txt` and `LICENSE.txt` in the package folder

## Links

- Website: https://osenpa.com
- App page: https://osenpa.com/veilclip
- Codeberg repository: https://codeberg.org/Osenpa/veilclip
- Donate: https://osenpa.com/donate
- Email: osenpacom@gmail.com

## Notes

- both release formats store user data in `%APPDATA%\VeilClip` by default
- JSON and CSV exports store image entries as placeholders rather than full image blobs
- image entries are skipped during JSON and CSV import
- Favorites remain independent from normal history deletion once saved

## Release Notes

- the portable ZIP includes `RELEASE.txt` and `LICENSE.txt` inside the package folder
