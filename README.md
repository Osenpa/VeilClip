# VeilClip

VeilClip is an open-source, offline clipboard manager for Windows 10 and Windows 11. It saves copied text, links, images, and file paths locally on your PC so you can search, pin, edit, reuse, and protect them later without a cloud account.

If you are looking for a Windows clipboard history app, a privacy-first clipboard manager, or a local-only clipboard tool, VeilClip is built for that exact use case.

## Quick Links

- Website: [osenpa.com](https://osenpa.com)
- App page: [osenpa.com/veilclip](https://osenpa.com/veilclip)
- Microsoft Store: [VeilClip](https://apps.microsoft.com/detail/9PLS27LJP9Q5)
- GitHub: [github.com/Osenpa/VeilClip](https://github.com/Osenpa/VeilClip)
- Codeberg: [codeberg.org/Osenpa/veilclip](https://codeberg.org/Osenpa/veilclip)
- Donate: [osenpa.com/donate](https://osenpa.com/donate)
- Contact: [osenpacom@gmail.com](mailto:osenpacom@gmail.com)

## Why VeilClip

Windows normally remembers only the last thing you copied. VeilClip keeps a searchable local history instead.

Main highlights:

- automatic clipboard history for text, links, images, and file paths
- fast search by content and source app
- pinned items and favorites with categories
- drag and drop back into other programs
- text editing, plain-text copy, and built-in image editing
- encrypted Locked Notes protected by a PIN
- local backup, export, and import tools
- multi-language interface
- offline-first behavior with no cloud dependency

## Privacy-First by Design

VeilClip is designed to stay local:

- no cloud sync
- no online account
- no telemetry in the current codebase
- no ads
- no internet connection required for normal use

Clipboard data is stored in a local SQLite database under `%APPDATA%\VeilClip` by default.

## Core Features

### Clipboard History

VeilClip monitors the Windows clipboard and saves:

- text
- links
- images
- file paths

Open the panel from the tray or with the default hotkey: `Alt+V`.

### Search, Grouping, and Reuse

- search by item text
- search by source application
- group history by app
- click any saved item to copy it back instantly
- drag clipboard cards directly into other apps

### Favorites and Locked Notes

Favorites help you keep reusable content close at hand. Locked Notes store sensitive text behind a PIN.

Favorites support:

- built-in categories: Work, Personal, Passwords, General
- custom categories
- independent storage from normal history
- click-to-copy and drag-and-drop
- right-click edit and remove actions

Locked Notes use encrypted local storage inside the VeilClip database.

### Editing Tools

- edit saved text
- copy as plain text
- edit saved images
- preview copied color values

### Backup, Export, and Import

- scheduled local database backups
- manual backup now
- export to JSON
- export to CSV
- import from JSON
- import from CSV

Notes:

- JSON and CSV are text-based export formats.
- Image entries are exported as `[image]` placeholders in JSON and CSV.
- Image entries are skipped during JSON and CSV import.
- Full database backups are the safest way to preserve everything.

## Supported Languages

VeilClip currently includes these UI languages:

| Code | Language |
| --- | --- |
| `en` | English |
| `de` | German |
| `fr` | French |
| `id` | Indonesian |
| `zh_CN` | Chinese (Simplified) |
| `ru` | Russian |
| `ko` | Korean |
| `ja` | Japanese |
| `es` | Spanish |
| `ar` | Arabic |
| `it` | Italian |
| `uk` | Ukrainian |
| `tr` | Turkish |
| `hi` | Hindi |
| `pt` | Portuguese |
| `pl` | Polish |

Arabic is supported as a right-to-left language.

## System Requirements

- Windows 10 or Windows 11
- Python 3.14 or another recent Python 3 version for source runs
- a desktop session with a system tray

Main runtime dependencies:

- `PyQt6`
- `pywin32`
- `Pillow`
- `psutil`
- `pycryptodome`

Packaged releases do not require Python.

## Downloads

VeilClip is released in two separate Windows formats through the repository release pages:

- Microsoft Store:
  - [VeilClip on Microsoft Store](https://apps.microsoft.com/detail/9PLS27LJP9Q5)
- Installer: `VeilClip-Setup-<version>.exe`
- Portable EXE ZIP: `VeilClip-Portable-<version>.zip`

Choose the installer if you want:

- guided setup
- Start Menu and desktop shortcuts
- automatic startup shortcut creation
- uninstall support from Windows

Choose the portable EXE ZIP if you want:

- no installer
- a self-contained folder you can extract anywhere
- `VeilClip.exe` plus `RELEASE.txt` and `LICENSE.txt` in the package

Both formats use `%APPDATA%\VeilClip` for user data by default.

## Run From Source

### 1. Clone the repository

```powershell
git clone https://github.com/Osenpa/VeilClip.git
cd veilclip
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Start VeilClip

```powershell
python main.py
```

When the app starts, it moves to the system tray and begins watching the clipboard immediately.

## Keyboard Shortcuts

| Shortcut | Action |
| --- | --- |
| `Alt+V` | Open or close the main panel |
| `Escape` | Close the panel or clear search |
| `Ctrl+Z` | Undo the most recent pending delete |

## Data Storage

Typical local paths:

- database: `%APPDATA%\VeilClip\data\data.db`
- logs: `%APPDATA%\VeilClip\logs\veilclip.log`
- settings: `%APPDATA%\VeilClip\config.json`

Notes:

- the database path can be changed in Settings
- clipboard history is stored in SQLite
- Locked Notes use encrypted storage inside the database
- installer and portable builds use the same AppData-based storage layout by default

## Release Files

Repository release tooling lives here:

- PyInstaller spec: `packaging/VeilClip.spec`
- Inno Setup script: `packaging/VeilClip.iss`
- build helper: `tools/build_installer.ps1`
- release notes and release-page copy: `releases/`
- release workflow notes: `docs/RELEASING.md`

## Project Structure

```text
VeilClip/
|- assets/      Icons and donation assets
|- core/        Clipboard, database, backup, export, vault logic
|- docs/        Maintainer documentation
|- locales/     Translation files
|- packaging/   PyInstaller and Inno Setup release files
|- releases/    Release notes and asset templates
|- tools/       Utility scripts
|- ui/          Windows and widgets
|- utils/       Shared helpers and config code
|- main.py      App entry point
```

## Open-Source Files

This repository includes:

- `README.md`
- `LICENSE`
- `CONTRIBUTING.md`
- `CHANGELOG.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- `SUPPORT.md`
- `.gitignore`
- `.editorconfig`

## Roadmap

- automated tests
- code signing for Windows releases
- safer upgrade guidance for packaged builds
- more import and export formats
- stronger release automation

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request or merge request.

## Security

If you find a security issue, read [SECURITY.md](SECURITY.md) and report it privately before opening a public issue.

## Support

If you need help, read [SUPPORT.md](SUPPORT.md).

## License

Released under the MIT License. See [LICENSE](LICENSE).
