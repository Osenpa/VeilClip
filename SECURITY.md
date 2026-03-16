# Security Policy

## Supported Versions

At this stage, security fixes are expected to focus on the newest active codebase.

| Version | Supported |
| --- | --- |
| Latest stable release | Yes |
| Older releases | Best effort |
| Unreleased local builds | No guarantee |

## How to Report a Security Problem

Please do **not** post security problems in a public Codeberg issue first.

Instead, report them privately:

- Email: `osenpacom@gmail.com`
- Website: `https://osenpa.com`

Use a subject like:

`[SECURITY] VeilClip vulnerability report`

Please include:

- a clear summary
- steps to reproduce
- affected version
- impact
- screenshots or logs if safe to share
- whether sensitive clipboard data is involved

## What Counts as a Security Issue

Examples:

- private clipboard data exposed to the wrong user
- Locked Notes bypass or PIN bypass
- unsafe storage of sensitive content
- unexpected network transmission
- code execution through clipboard content
- backup or import behavior that leaks private data

## What to Expect

When a valid report arrives, maintainers should:

- review the report
- reproduce the problem if possible
- plan a fix
- coordinate safe disclosure
- publish a fix or mitigation note when appropriate

## Privacy Notes

VeilClip is designed to work offline and keep data local, but local privacy still matters.

Please remember:

- clipboard history can contain passwords, tokens, links, and personal data
- logs should never be shared without checking them first
- exported files may contain sensitive text
- database backups may contain sensitive history

## Safe Sharing Tips

Before sharing files for debugging:

- remove private text
- blur screenshots if needed
- avoid sending full databases unless absolutely necessary
- never post secrets in public threads
