# Contributing to VeilClip

Thank you for helping improve VeilClip, the open-source offline clipboard manager for Windows.

This guide is written to be clear and simple. If you want to fix a bug, improve the UI, add a language, or write better docs, you are welcome here.

## Before You Start

Please read these files first:

- `README.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`

If your report is about a security problem, do **not** open a public issue first. Follow `SECURITY.md`.

## Good First Ways to Help

You can help by:

- fixing bugs
- improving performance
- cleaning up code
- writing tests
- improving documentation
- improving translations
- improving accessibility and usability

## Local Setup

### 1. Clone the project

```powershell
git clone https://github.com/Osenpa/VeilClip.git
cd veilclip
```

### 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Run the app

```powershell
python main.py
```

## Development Rules

Please keep changes:

- small when possible
- easy to review
- easy to understand
- consistent with the current app style

### Code Style

Follow these rules:

- use clear names
- keep functions focused
- avoid large unrelated refactors in bug-fix pull requests
- prefer simple code over clever code
- keep comments short and useful
- preserve the Windows-first behavior of the app

### UI Changes

If you change the interface:

- keep the design readable
- test on normal desktop screen sizes
- check tray behavior
- check keyboard flow
- check English text carefully

### Translation Changes

If you add or update translations:

- keep the meaning close to English
- use short, simple sentences
- avoid changing translation keys without a good reason
- make sure the app still works when English is the fallback

## How to Report a Bug

Open a repository issue and include:

- what you expected to happen
- what actually happened
- steps to reproduce
- your Windows version
- your Python version
- screenshots if helpful
- log details if helpful

Useful places:

- runtime log: `%APPDATA%\VeilClip\logs\veilclip.log`
- local database: `%APPDATA%\VeilClip\data\data.db`

Do not share private clipboard data unless you have removed sensitive details.

## How to Suggest a Feature

Open a feature request if you want to suggest:

- a new clipboard feature
- a UI improvement
- a new export option
- a new language
- a workflow improvement

Explain:

- the problem
- your idea
- who it helps
- how it should work

## Pull Request Process

1. Create a branch for your work.
2. Make one focused change or one small group of related changes.
3. Test your change manually.
4. Update docs if behavior changed.
5. Open a pull request or merge request with a clear title and description.

Good pull requests usually include:

- a short summary
- why the change matters
- before and after notes
- screenshots for UI changes
- testing notes

## Testing Checklist

Please test the parts you changed.

Common manual checks:

- app starts correctly
- tray icon appears
- `Alt+V` opens the panel
- copied text appears in history
- copied image appears in history
- search works
- pinning works
- favorites work
- favorite stays visible after the original history item is deleted
- favorites search returns expected results
- favorite click copies correctly
- favorite drag-and-drop works
- favorite right-click actions work
- favorite removal asks for confirmation
- export works
- settings still save
- Windows startup works from the Startup shortcut

If your change touches packaging or startup behavior, also test:

- installer build completes
- portable ZIP build completes
- installed app launches after setup
- uninstall removes VeilClip files and data cleanly

If your change touches Locked Notes, also test:

- PIN setup
- unlock
- add note
- reopen and read note

## Commit Message Tips

Simple commit messages are best.

Examples:

- `fix: stop duplicate image save on clipboard refresh`
- `docs: add setup and privacy details to readme`
- `feat: add polish locale updates`

## Documentation Changes

If behavior changes, update the matching docs:

- `README.md`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `SUPPORT.md`
- release notes in `releases/` if a packaged release changed

## What Not to Do

Please avoid:

- unrelated formatting-only pull requests across many files
- mixing bug fixes and big rewrites in one PR
- adding new dependencies without explaining why
- removing privacy-focused behavior without discussion

## Questions

If you are not sure where to start, open a repository issue or use the support guidance in `SUPPORT.md`.

Thank you for helping make VeilClip better.
