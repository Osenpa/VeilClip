# Changelog

All notable changes to VeilClip will be documented in this file.

This project follows a simple human-readable changelog format so users can quickly see what changed.

## [Unreleased]

### Added

- Codeberg-ready repository metadata and release-document templates
- portable package release note template for bundled `RELEASE.txt`
- maintainer release workflow documentation

### Changed

- repository documentation now points to Codeberg, the project website, the donate page, and the support email
- release preparation now targets separate installer and portable EXE ZIP assets

### Removed

- local build artifacts and other machine-specific files from the intended repository contents

## [1.0.0] - 2026-03-15

### Added

- Windows system tray clipboard manager built with Python and PyQt6
- automatic clipboard history saving for text, links, images, and file paths
- global hotkey support with `Alt+V` as the default shortcut
- search for clipboard content and source app names
- pinned items that stay at the top of history
- grouped history view by source application
- multi-select mode for bulk actions
- undo support for recent deletions
- text editing and plain-text copy tools
- built-in image editor
- favorites with built-in and custom categories
- encrypted Locked Notes protected by a PIN
- automatic local database backups
- JSON and CSV export and import support
- multi-language UI with 16 bundled languages
- help, donate, and settings windows
- local logging and configurable storage location
- Windows installer and portable release outputs
- install-time default language selection
- install-time custom destination-folder selection
- uninstall entry with publisher and support metadata for Osenpa

### Changed

- Windows startup uses the user Startup folder shortcut instead of the registry Run key
- packaged builds store runtime data under `%APPDATA%\VeilClip` for stable installer and portable behavior
- favorites now keep their own stored copy of item content after being saved
- favorite cards now support click-to-copy and drag-and-drop like normal clipboard cards
- Favorites now include their own search bar, removal confirmation, and right-click edit actions
- changing the app language now restarts VeilClip and reopens the main window automatically

### Fixed

- deleting a clipboard-history item no longer removes the same item from Favorites
- packaged startup behavior is more reliable for installed builds
- packaged releases no longer depend on the `keyboard` hook library for the global hotkey
- editing favorite text no longer falls back into the copy-to-close behavior after the favorites list refreshes
- favorites removal confirmation text is now localized across the bundled non-English language packs
- settings/help/donate window titles no longer show a duplicate trailing VeilClip name on Windows
- dialog and editor title bars now use the VeilClip app icon consistently
- the image editor window title now avoids repeating VeilClip in the title bar

### Security

- fully offline local-first design
- local SQLite storage
- AES-256-CBC plus HMAC protection for Locked Notes
- PBKDF2-based key derivation for vault access

### Notes

- JSON and CSV exports store image entries as placeholders, not full image blobs
- image entries are skipped during JSON and CSV import
- Favorites are intentionally independent from clipboard-history deletion once saved

## Future Releases

New versions should add entries under a new heading like this:

```markdown
## [1.0.1] - YYYY-MM-DD
### Fixed
- Short human-readable note
```
