# Support

## Need Help With VeilClip?

This file explains the fastest way to get help with VeilClip.

## Where to Ask for Help

Use one of these options:

- open a Codeberg issue for bugs or feature ideas
- email `osenpacom@gmail.com` for private questions
- visit [osenpa.com/veilclip](https://osenpa.com/veilclip) for app details
- visit [osenpa.com](https://osenpa.com) for general project details
- visit [osenpa.com/donate](https://osenpa.com/donate) if you want to support development

Publisher for packaged Windows releases: `Osenpa`

## Before You Ask

Please check:

- `README.md`
- `CONTRIBUTING.md`
- `SECURITY.md`

## Information That Helps a Lot

When asking for help, please include:

- what you were trying to do
- what happened instead
- how to repeat the problem
- your Windows version
- your Python version
- screenshots if helpful

If possible, also include:

- current app language
- whether the problem happened with text, image, link, or file path clipboard data
- whether Locked Notes, backup, export, or import were involved
- whether you used the installer build or the portable build
- whether the problem happens only after Windows startup or also after a manual launch

## Useful Local Files

You may be asked to check:

- log file: `%APPDATA%\VeilClip\logs\veilclip.log`
- database file: `%APPDATA%\VeilClip\data\data.db`
- settings file: `%APPDATA%\VeilClip\config.json`
- Windows startup shortcut: `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\VeilClip.lnk`

Check these files before sharing them. They may contain private information.

## Install and Uninstall Notes

If you installed VeilClip with the setup file:

- Windows will show the publisher as `Osenpa`
- uninstall is available from Windows Apps / Control Panel
- uninstall is designed to remove the app, its startup shortcut, and VeilClip user data

If you are using the portable ZIP build:

- deleting the extracted folder does not remove `%APPDATA%\VeilClip`
- remove `%APPDATA%\VeilClip` manually if you want a fully clean local reset

## Bug Report or Feature Request?

Use:

- a **bug report** when something is broken
- a **feature request** when you want something new or better

The primary public tracker for VeilClip is the Codeberg issue tracker.

## Security Problems

If your problem is about privacy or security, do **not** open a public issue first.

Follow `SECURITY.md`.
