"""
utils/text_cleaner.py
─────────────────────
Utilities for detecting and stripping rich-text formatting (HTML / RTF)
from clipboard content, and for copying cleaned text to the system clipboard.
"""

import re
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

logger = logging.getLogger(__name__)

# ── Regex patterns ────────────────────────────────────────────────────────────

# Matches any HTML/XML tag
_RE_HTML_TAG   = re.compile(r"<[^>]+>", re.DOTALL)

# Matches HTML entities: &amp; &#160; &#x00A0; etc.
_RE_HTML_ENT   = re.compile(r"&(?:#\d+|#x[\dA-Fa-f]+|[A-Za-z]{2,8});")

# Matches RTF control words: \rtf1  \b  \par  \u8203?  etc.
_RE_RTF_CTRL   = re.compile(r"\\[a-zA-Z]+\d*\s?")

# Matches RTF curly-brace groups and stray braces
_RE_RTF_BRACES = re.compile(r"[{}]")

# Matches RTF hex escapes: \'XX
_RE_RTF_HEX    = re.compile(r"\\'[0-9A-Fa-f]{2}")

# Collapse runs of whitespace (spaces / tabs) to a single space
_RE_SPACES     = re.compile(r"[ \t]+")

# Collapse more than two consecutive newlines to two
_RE_NEWLINES   = re.compile(r"\n{3,}")

# Quick detection patterns
_HTML_DETECT   = re.compile(r"<(?:html|head|body|div|span|p|br|table|font|style|script)\b", re.I)
_TAG_DETECT    = re.compile(r"<[a-zA-Z/][^>]{0,200}>")
_RTF_DETECT    = re.compile(r"^\s*\{?\\rtf", re.I)

# Common HTML entities → plain chars
_HTML_ENTITIES = {
    "&amp;":  "&",
    "&lt;":   "<",
    "&gt;":   ">",
    "&quot;": '"',
    "&apos;": "'",
    "&nbsp;": " ",
    "&copy;": "©",
    "&reg;":  "®",
    "&mdash;": "—",
    "&ndash;": "–",
    "&hellip;": "…",
    "&laquo;": "«",
    "&raquo;": "»",
}


# ── Public API ────────────────────────────────────────────────────────────────

def is_rich_text(text: str) -> bool:
    """
    Return True if *text* appears to contain HTML or RTF markup.

    Detection is intentionally conservative — plain text that happens
    to include angle brackets (e.g. generics in code) will not be
    flagged unless it also has recognisable tag structure.
    """
    if not text:
        return False

    # RTF always starts with {\rtf
    if _RTF_DETECT.search(text):
        return True

    # HTML: well-known block/inline tags
    if _HTML_DETECT.search(text):
        return True

    # Looser: any balanced-looking tag with optional attributes
    if _TAG_DETECT.search(text):
        return True

    return False


def strip_formatting(text: str) -> str:
    """
    Remove HTML tags, RTF control sequences, and excess whitespace.
    Returns clean plain text.

    Handles:
    - HTML tags and common HTML entities
    - RTF control words, hex escapes, and curly-brace groups
    - Leading/trailing whitespace on every line
    - Collapsed blank lines (max 1 blank line between paragraphs)
    """
    if not text:
        return ""

    result = text

    # ── RTF ──────────────────────────────────────────────────────────────────
    if _RTF_DETECT.search(result):
        result = _RE_RTF_HEX.sub("", result)       # \'XX hex escapes
        result = _RE_RTF_CTRL.sub(" ", result)     # \controlword
        result = _RE_RTF_BRACES.sub("", result)    # { }

    # ── HTML entities (named) ─────────────────────────────────────────────────
    for entity, char in _HTML_ENTITIES.items():
        result = result.replace(entity, char)

    # ── Numeric HTML entities (&#NNN; / &#xHH;) ──────────────────────────────
    def _decode_entity(m: re.Match) -> str:
        s = m.group(0)
        try:
            if s.startswith("&#x") or s.startswith("&#X"):
                return chr(int(s[3:-1], 16))
            if s.startswith("&#"):
                return chr(int(s[2:-1]))
        except (ValueError, OverflowError):
            pass
        return ""

    result = _RE_HTML_ENT.sub(_decode_entity, result)

    # ── HTML tags ─────────────────────────────────────────────────────────────
    # Replace <br>, <p>, </p>, </div>, <li> with newlines before stripping
    result = re.sub(r"<br\s*/?>", "\n", result, flags=re.I)
    result = re.sub(r"</?(p|div|li|tr|h[1-6])\b[^>]*>", "\n", result, flags=re.I)
    result = _RE_HTML_TAG.sub("", result)

    # ── Whitespace normalisation ───────────────────────────────────────────────
    lines = [_RE_SPACES.sub(" ", line).strip() for line in result.splitlines()]
    result = "\n".join(lines)
    result = _RE_NEWLINES.sub("\n\n", result)
    result = result.strip()

    return result


def copy_as_plain_text(item_id: int, db) -> bool:
    """
    Fetch item *item_id* from *db*, strip any rich-text formatting,
    and place the result on the system clipboard as plain text.

    Returns True on success, False on failure.

    Parameters
    ----------
    item_id : int
        The database row id of the clipboard item.
    db : core.database.Database
        An open Database instance.
    """
    try:
        from PyQt6.QtWidgets import QApplication

        # Retrieve all items and find the one we want
        # (Database doesn't expose get_by_id yet, so we filter in Python)
        items = db.get_all_items()
        item  = next((i for i in items if i["id"] == item_id), None)

        if item is None:
            logger.warning("copy_as_plain_text: item id=%s not found.", item_id)
            return False

        if item["content_type"] == "image":
            logger.info("copy_as_plain_text: item id=%s is an image — skipped.", item_id)
            return False

        raw   = item.get("content_text") or ""
        clean = strip_formatting(raw) if is_rich_text(raw) else raw

        app = QApplication.instance()
        if app is None:
            logger.error("copy_as_plain_text: No QApplication found.")
            return False

        app.clipboard().setText(clean)
        logger.debug(
            "copy_as_plain_text: id=%s copied (%d → %d chars).",
            item_id, len(raw), len(clean),
        )
        return True

    except Exception as exc:
        logger.error("copy_as_plain_text failed: %s", exc)
        return False


# ── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s  %(message)s")

    samples = [
        # (label, text)
        ("Plain",        "Hello, world!"),
        ("HTML basic",   "<p>Hello <b>world</b></p>"),
        ("HTML full",    "<html><body><div class='x'><p>Para &amp; text</p><br/></div></body></html>"),
        ("HTML entity",  "Price: &pound;10 &mdash; buy &amp; sell &lt;now&gt;"),
        ("RTF",          r"{\rtf1\ansi\deff0{\fonttbl{\f0 Arial;}}\f0\fs24 Hello \b world\b0\par}"),
        ("Multi-space",  "Too   many    spaces\tand\ttabs"),
        ("Multi-line",   "Line 1\n\n\n\nLine 2\n\n\n\nLine 3"),
    ]

    for label, text in samples:
        rich = is_rich_text(text)
        clean = strip_formatting(text)
        print(f"\n{'─'*60}")
        print(f"[{label}]  is_rich_text={rich}")
        print(f"  IN : {text[:80]!r}")
        print(f"  OUT: {clean!r}")