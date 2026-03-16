"""
core/source_detector.py
───────────────────────
Detect the name of the application that currently owns the clipboard /
has foreground focus.

For browser windows the window title is parsed to extract the page/site
name so clipboard entries show something useful instead of just "Chrome".
"""

import logging
import re
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

# ── Friendly process-name map ─────────────────────────────────────────────────

_PROCESS_MAP: dict[str, str] = {
    "chrome.exe":          "Google Chrome",
    "msedge.exe":          "Microsoft Edge",
    "firefox.exe":         "Firefox",
    "brave.exe":           "Brave",
    "opera.exe":           "Opera",
    "vivaldi.exe":         "Vivaldi",
    "safari.exe":          "Safari",
    "iexplore.exe":        "Internet Explorer",
    "notepad.exe":         "Notepad",
    "notepad++.exe":       "Notepad++",
    "code.exe":            "VS Code",
    "devenv.exe":          "Visual Studio",
    "pycharm64.exe":       "PyCharm",
    "idea64.exe":          "IntelliJ IDEA",
    "sublime_text.exe":    "Sublime Text",
    "atom.exe":            "Atom",
    "wordpad.exe":         "WordPad",
    "winword.exe":         "Microsoft Word",
    "excel.exe":           "Microsoft Excel",
    "powerpnt.exe":        "Microsoft PowerPoint",
    "onenote.exe":         "OneNote",
    "outlook.exe":         "Outlook",
    "thunderbird.exe":     "Thunderbird",
    "slack.exe":           "Slack",
    "discord.exe":         "Discord",
    "teams.exe":           "Microsoft Teams",
    "telegram.exe":        "Telegram",
    "whatsapp.exe":        "WhatsApp",
    "explorer.exe":        "File Explorer",
    "cmd.exe":             "Command Prompt",
    "powershell.exe":      "PowerShell",
    "wt.exe":              "Windows Terminal",
    "windowsterminal.exe": "Windows Terminal",
    "mspaint.exe":         "Paint",
    "photoshop.exe":       "Photoshop",
    "figma.exe":           "Figma",
}

# Browsers whose window titles can be parsed for site name
_BROWSER_EXES = {
    "chrome.exe", "msedge.exe", "firefox.exe",
    "brave.exe",  "opera.exe",  "vivaldi.exe",
}

# Patterns to strip browser suffix from window title:
#   "GitHub · Build software · GitHub — Google Chrome"
#   "Stack Overflow - Where Developers Learn — Mozilla Firefox"
_BROWSER_SUFFIX_RE = re.compile(
    r"\s*[-—|–]\s*(?:Google Chrome|Mozilla Firefox|Microsoft Edge|"
    r"Brave|Opera|Vivaldi|Safari|Internet Explorer)\s*$",
    re.IGNORECASE,
)


_PSUTIL_AVAILABLE: bool | None = None   # None = not yet checked


def _check_psutil() -> bool:
    """Return True if psutil is importable. Logs a single warning if not."""
    global _PSUTIL_AVAILABLE
    if _PSUTIL_AVAILABLE is None:
        try:
            import psutil  # noqa: F401
            _PSUTIL_AVAILABLE = True
        except ImportError:
            _PSUTIL_AVAILABLE = False
            logger.warning(
                "psutil is not installed — source-app detection is disabled. "
                "Run: pip install psutil"
            )
    return _PSUTIL_AVAILABLE


def get_active_app_name() -> str:
    """
    Return a human-readable name for the foreground application.

    Tries psutil + win32 first (full exe name lookup), then falls back
    to win32-only (window title) so we always get something useful.

    Returns "Unknown" only if all detection fails.
    """
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return "Unknown"
        window_title = win32gui.GetWindowText(hwnd) or ""
    except Exception:
        return "Unknown"

    # ── Full detection via psutil ──────────────────────────────────────────
    if _check_psutil():
        try:
            import win32process
            import psutil

            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            exe  = proc.name().lower()

            if exe in _BROWSER_EXES:
                site = _extract_site_from_title(window_title, exe)
                if site:
                    return site
                return _PROCESS_MAP.get(exe, _clean_exe(exe))

            if exe in _PROCESS_MAP:
                return _PROCESS_MAP[exe]

            if window_title:
                return window_title.split(" - ")[-1].strip()[:40] or _clean_exe(exe)
            return _clean_exe(exe)

        except Exception as exc:
            logger.debug("psutil source detection failed: %s", exc)
            # Fall through to window-title fallback

    # ── Fallback: use window title (no psutil needed) ──────────────────────
    if window_title:
        # Most apps format title as "Document - AppName" — grab last segment
        parts = [p.strip() for p in window_title.replace("—", "-").split("-") if p.strip()]
        if parts:
            return parts[-1][:40]
    return "Unknown"


def _extract_site_from_title(title: str, exe: str) -> str | None:
    """
    Parse the browser window title to return a site/page identifier.

    Most browsers format titles as:
        "Page Title - Site Name — Browser Name"
    We strip the browser suffix and return what's left, truncated.
    """
    if not title:
        return None

    # Remove trailing browser name
    cleaned = _BROWSER_SUFFIX_RE.sub("", title).strip()
    if not cleaned:
        return None

    # If the remaining text looks like a URL, just return the domain
    if cleaned.startswith(("http://", "https://")):
        try:
            from urllib.parse import urlparse
            host = urlparse(cleaned).netloc.removeprefix("www.")
            return host or cleaned[:50]
        except Exception:
            pass

    # Return cleaned title, capped at 50 chars
    return cleaned[:50] if cleaned else None


def _clean_exe(exe: str) -> str:
    """'myapp.exe' → 'Myapp'"""
    name = exe.removesuffix(".exe")
    return name.capitalize() if name else "Unknown"


# ── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format="%(levelname)s  %(message)s")
    print("Foreground app:", get_active_app_name())