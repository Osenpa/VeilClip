from __future__ import annotations

import ast
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deep_translator import GoogleTranslator

from ui.help_window import HELP_SECTIONS

LOCALES_DIR = ROOT / "locales"

TARGETS = {
    "de": "de",
    "fr": "fr",
    "id": "id",
    "zh_CN": "zh-CN",
    "ru": "ru",
    "ko": "ko",
    "ja": "ja",
    "es": "es",
    "ar": "ar",
    "it": "it",
    "uk": "uk",
    "tr": "tr",
    "hi": "hi",
    "pt": "pt",
    "pl": "pl",
}

MASK_RE = re.compile(
    r"("
    r"\{[^}]+\}"
    r"|https?://\S+"
    r"|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    r"|osenpa\.com"
    r"|VeilClip"
    r"|PyQt6"
    r"|Alt\+V"
    r"|Ctrl\+[A-Z]"
    r"|Escape"
    r"|</?[^>]+>"
    r"|&amp;"
    r")"
)

MOJIBAKE_HINTS = ("Ã", "â", "ğŸ", "œ", "€", "™", "�")
SKIP_FILES = {"ui/help_window.py", "main.py"}
SKIP_EXACT = {
    "__main__",
    "json",
    "csv",
    "pano",
    "favorites",
    "ctrl",
    "alt",
    "shift",
    "tool",
    "title",
    "body",
    "name",
    "label",
    "code",
    "native_name",
    "id",
    "step",
    "main.py",
    "utf-8",
    "locales",
}
STYLE_MARKERS = (
    "QPushButton",
    "QWidget",
    "QDialog",
    "QLabel",
    "QLineEdit",
    "QScrollArea",
    "QScrollBar",
    "QToolBar",
    "QMenu",
    "QStatusBar",
    "QSpinBox",
    "font-family",
    "background:",
    "border:",
    "padding:",
    "spacing:",
    "color:",
    "min-width:",
    "max-width:",
    "border-radius:",
    "Segoe UI",
    "Consolas",
    "font-size:",
    "font-weight:",
    "QMessageBox",
)
SINGLE_WORD_KEEP = {
    "About",
    "All",
    "Auto-Delete",
    "Backup",
    "Basics",
    "Cancel",
    "Clipboard",
    "Close",
    "Color",
    "Copy",
    "Crypto",
    "Data",
    "Delete",
    "Dash",
    "Email",
    "Exit",
    "Export",
    "Favorites",
    "Help",
    "Hide",
    "History",
    "Hotkey",
    "Import",
    "Languages",
    "Lock",
    "Manage",
    "OK",
    "OFF",
    "ON",
    "Open",
    "Privacy",
    "Rename",
    "Search",
    "Select",
    "Settings",
    "Show",
    "Storage",
    "Undo",
    "Website",
    "Window",
}

MANUAL_LITERALS = [
    "Help & Support",
    "A complete guide to VeilClip — 20 sections covering every feature. Read any section you need, or start from the beginning.",
    "100 % Offline",
    "Local Storage Only",
    "Open-Source",
    "Free Forever",
    "Get in Touch",
    "If you have a question, found a bug, or just want to say hello, reach out through the channels below. Every message is read.",
    "Email",
    "Website",
    "Support VeilClip",
    "VeilClip is free and open-source. If you find it useful,\nconsider buying the developer a coffee or donating crypto. 🙏",
    "Buy Me a Coffee",
    "Crypto",
    "The quickest way to show appreciation!",
    "Click to copy",
    "Click to open in browser",
    "Click to copy address",
    "✓ Copied",
    "✓  Copied!",
    "Bitcoin (BTC/SegWit)",
    "Ethereum (ERC-20)",
    "USDT (Tron / TRC-20)",
    "USDT (Ethereum / ERC-20)",
    "USDC (Ethereum / ERC-20)",
    "USDC (Solana)",
    "BNB (BEP-20)",
    "Solana (SOL)",
    "Dash",
    "Litecoin (LTC)",
    "Cardano (ADA)",
    "Dogecoin (DOGE)",
    "Bitcoin Cash (BCH)",
    "⚠  BCH only — do NOT send regular Bitcoin (BTC) to this address.",
]

BASE_LOCALE = {
    "app": {
        "tagline": "VeilClip — The Stealth & Offline Clipboard for Windows",
    },
    "tray": {
        "open": "Open VeilClip",
        "settings": "Settings",
        "clear_history": "Clear History",
        "donate": "Donate",
        "help": "Help",
        "exit": "Exit",
        "tooltip": "VeilClip — The Stealth & Offline Clipboard for Windows",
    },
    "common": {
        "ok": "OK",
        "yes": "Yes",
        "no": "No",
        "cancel": "Cancel",
        "copy": "Copy",
        "delete": "Delete",
        "rename": "Rename",
        "close": "Close",
        "show": "Show",
        "hide": "Hide",
        "add": "Add",
        "undo": "Undo",
        "unknown": "Unknown",
    },
    "dialogs": {
        "confirm_clear_title": "Clear History",
        "confirm_clear_body": "Delete all unpinned clipboard history?\nThis cannot be undone.",
    },
    "errors": {
        "system_tray_unavailable": "System tray is not available.",
    },
    "notifications": {
        "started": "VeilClip is running in the background.",
        "history_cleared": "Clipboard history has been cleared.",
        "hotkey_changed": "Hotkey updated to {hotkey}.",
        "auto_cleanup_removed": "Auto-cleanup removed {count} old items.",
        "copied": "✓ Copied!",
        "copied_plain": "✓ Copied as Plain Text!",
        "image_copied": "✓ Image Copied!",
        "copied_value": "✓ Copied {value}!",
        "text_updated": "✓ Text updated!",
    },
    "language": {
        "change_title": "Change language",
        "change_body": "Switch VeilClip to {language}? The app will restart to apply the change everywhere.",
    },
    "time": {
        "just_now": "just now",
        "minutes_ago": "{count}m ago",
        "hours_ago": "{count}h ago",
        "days_ago": "{count}d ago",
    },
    "main": {
        "title": "VeilClip",
        "count_items": "{count} items",
        "selected_count": "{count} selected",
        "empty_default": "Copy something to get started",
        "no_results": "No results for \"{query}\"",
        "no_favorites_title": "No favorites yet",
        "no_favorites_hint": "Right-click any clipboard item\nand choose Add to Favorites.",
        "welcome_message": "Everything you copy shows up here. Press Alt+V to open VeilClip at any time.",
        "group_pinned": "📌  Pinned",
        "deleted_single": "Deleted —",
        "deleted_pending": "Deleted ({count} pending) —",
        "multicopy_done": "✓ {count} items copied!",
        "multicopy_mixed": "✓ {copied} copied, {skipped} image items skipped",
        "multicopy_images_only": "Images cannot be copied this way",
    },
    "favorites": {
        "all": "All",
        "manage": "Manage",
        "count": "{count} favorites",
        "category_saved": "{category} (already saved)",
        "saved_to": "★ Saved to {category}!",
        "manage_title": "Manage Categories",
        "manage_hint": "Rename or delete favorite categories.",
        "rename_title": "Rename",
        "rename_prompt": "New name for \"{category}\":",
        "delete_title": "Delete Category",
        "delete_body": "\"{category}\" category will be permanently deleted. Are you sure?",
        "categories": {
            "work": "Work",
            "personal": "Personal",
            "passwords": "Passwords",
            "general": "General",
        },
    },
    "item_card": {
        "tooltips": {
            "click_to_copy": "Click to copy",
            "copy_color": "Copy {value}",
            "pin_toggle": "Pin / Unpin",
        },
        "preview": {
            "image": "[Image]",
        },
        "counts": "{chars}c  {words}w",
        "edit_title": "Edit Text",
        "edit_hint": "Edit text below. Changes replace the clipboard entry.",
    },
    "backup": {
        "messages": {
            "no_directory": "No backup directory configured.",
            "create_dir_failed": "Could not create the backup folder: {detail}",
            "db_missing": "Database not found: {path}",
            "copy_failed": "Backup copy failed: {detail}",
            "completed": "Backup created: {filename}",
        },
    },
    "export": {
        "messages": {
            "exported": "Exported {count} items.",
            "export_failed": "Export failed: {detail}",
            "invalid_json": "Invalid JSON format.",
            "import_failed": "Import failed: {detail}",
            "imported": "Imported {imported} items. Skipped {skipped}.",
        },
    },
    "settings": {
        "window_title": "{app} — Settings",
        "path_changed_title": "Path Changed",
        "path_changed_body": "Database path set to:\n{path}\n\nVeilClip must be restarted for the new database to be used.\nYour existing history is not moved automatically.",
        "path_reset_title": "Path Reset",
        "path_reset_body": "Database path has been reset to the default location.\nRestart VeilClip to apply the change.",
        "backup_manager_unavailable": "Backup manager not available.",
        "database_unavailable": "Database not available.",
        "export_as": "Export as {format}",
        "import_file": "Import {format}",
        "startup_error_title": "Startup",
        "startup_error_body": "Could not update the Windows registry.\nTry running VeilClip as Administrator.",
        "clear_history_title": "Clear History",
        "clear_history_body": "Delete all unpinned clipboard history?\nThis cannot be undone.",
        "clear_pinned_title": "Clear Pinned",
        "clear_pinned_body": "Delete all pinned items?\nThis cannot be undone.",
        "auto_delete_hours_label": "Delete items older than  {count} hour(s)",
        "auto_delete_days_label": "Delete items older than  {count} day(s)",
    },
    "vault": {
        "window_title": "VeilClip — Locked Notes",
        "set_pin_title": "Set a PIN",
        "set_pin_desc": "Choose a PIN or passphrase to protect your Locked Notes.\nIf you forget it, your notes cannot be recovered.",
        "set_pin_action": "Set PIN",
        "enter_pin": "Locked Notes — Enter PIN",
        "unlock_action": "Unlock",
        "main_title": "Locked Notes",
        "lock_action": "Lock",
        "change_pin_action": "Change PIN",
        "paste_action": "Paste from clipboard",
        "no_items": "No locked notes yet.",
        "no_label": "(no label)",
        "delete_item": "Delete Note",
        "delete_confirm": "Permanently delete this note?",
        "current_pin": "Current PIN:",
        "new_pin": "New PIN:",
        "confirm_new_pin": "Confirm new PIN:",
        "pin_changed": "PIN changed successfully.",
        "errors": {
            "pin_empty": "PIN cannot be empty.",
            "pin_mismatch": "PINs do not match.",
            "try_again_in": "Too many wrong attempts. Try again in {seconds}s.",
            "locked_for": "Too many wrong attempts. Locked for {seconds} seconds.",
            "incorrect_pin": "Incorrect PIN. {count} attempts left.",
            "secret_empty": "Secret text cannot be empty.",
            "clipboard_empty": "Clipboard is empty.",
            "current_pin_incorrect": "Current PIN is incorrect.",
        },
    },
    "image_editor": {
        "save_as": "Save Image As",
        "save_failed_title": "Save Failed",
        "save_failed_body": "Could not save to:\n{path}",
        "tools": {
            "crop": "Crop",
            "arrow": "Arrow",
            "highlight": "Highlight",
            "text": "Text",
        },
        "hints": {
            "crop": "Click and drag to select the crop area.",
            "arrow": "Click and drag to draw an arrow.",
            "highlight": "Click and drag to highlight an area.",
            "text": "Click to add text. Drag existing text to move it. Right-click to edit, recolor, resize, or delete it.",
        },
        "status": {
            "ready": "Image: {width} × {height} px — Select a tool and interact with the image.",
            "tool_selected": "Tool: {tool} — {hint}",
            "text_updated": "Text updated: \"{text}\"",
            "text_deleted": "Text item deleted.",
            "text_placed": "Text placed: \"{text}\" — drag to move, right-click to edit.",
            "crop_too_small": "Selection too small to crop.",
            "selection_too_small": "Selection too small.",
            "arrow_drawn": "Arrow drawn.",
            "saved": "Saved: {path}",
            "text_item_removed": "Text item removed.  ({count} raster step(s) remaining)",
            "nothing_to_undo": "Nothing to undo.",
            "undo_done": "Undo.  ({count} step(s) remaining)",
            "cropped": "Cropped to {width} × {height} px.",
            "highlighted": "Highlighted {width} × {height} px.",
            "undo_remaining": "  |  Undo: {count} step(s)",
        },
    },
    "help": {
        "window_title": "{app} — Help & Support",
        "sections": HELP_SECTIONS,
    },
    "donate": {
        "window_title": "{app} — Support the Developer",
    },
}


def _weird_score(text: str) -> int:
    score = text.count("\ufffd")
    score += sum(text.count(marker) for marker in MOJIBAKE_HINTS)
    return score


def repair_text(text: str) -> str:
    if not text:
        return text

    best = text
    for encoding in ("cp1252", "cp1254", "latin1"):
        try:
            candidate = text.encode(encoding).decode("utf-8")
        except Exception:
            continue
        if _weird_score(candidate) < _weird_score(best):
            best = candidate
    return best


def repair_value(value: Any) -> Any:
    if isinstance(value, str):
        return repair_text(value)
    if isinstance(value, list):
        return [repair_value(item) for item in value]
    if isinstance(value, dict):
        return {key: repair_value(item) for key, item in value.items()}
    return value


def docstring_positions(tree: ast.AST) -> set[tuple[int, int]]:
    positions: set[tuple[int, int]] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            positions.add((first.value.lineno, first.value.col_offset))
    return positions


def main_block_ranges(tree: ast.AST) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for node in getattr(tree, "body", []):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not isinstance(test, ast.Compare):
            continue
        if not isinstance(test.left, ast.Name) or test.left.id != "__name__":
            continue
        if len(test.comparators) != 1:
            continue
        comp = test.comparators[0]
        if not isinstance(comp, ast.Constant) or comp.value != "__main__":
            continue
        ranges.append((node.lineno, node.end_lineno or node.lineno))
    return ranges


def should_skip_literal(text: str) -> bool:
    if not text or text in SKIP_EXACT:
        return True
    if not any(ch.isalpha() for ch in text):
        return True
    if text.startswith(".") or text.startswith("-"):
        return True
    if text.startswith("#") or text.startswith("%"):
        return True
    if text in {"<b>", "</b>  v"}:
        return True
    if "{" in text or "}" in text:
        return True
    if any(marker in text for marker in STYLE_MARKERS):
        return True
    if "%s" in text or "%d" in text:
        return True
    if re.search(r"https?://", text):
        return True
    if re.fullmatch(r"(Ctrl|Alt)\+[A-Z]", text):
        return True
    if re.fullmatch(r"\d+\s*h", text):
        return True
    if re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text):
        return True
    if re.fullmatch(r"#[0-9A-Fa-f]{3,8}", text):
        return True
    if len(text) > 18 and " " not in text and re.fullmatch(r"[A-Za-z0-9:/._\\\-()*.]+", text):
        return True
    if re.fullmatch(r"[a-z_][a-z0-9_./\\-]*", text):
        return True
    if text.startswith("DELETE FROM ") or text == "VACUUM":
        return True
    if text.startswith("PyQt6."):
        return True
    if text.startswith("ImageEditorWindow:"):
        return True
    if text.endswith(" triggered") or text.endswith(" callback not set."):
        return True
    if "px dashed" in text or "px solid" in text:
        return True
    if text.isidentifier() and text not in SINGLE_WORD_KEEP:
        return True
    if " " not in text and "\n" not in text and text.upper() == text and text not in {"ON", "OFF", "OK"}:
        return True
    if text.startswith(";") or text.endswith("=>"):
        return True
    return False


def collect_literals() -> dict[str, str]:
    literals: dict[str, str] = {}
    for path in sorted(ROOT.glob("ui/*.py")) + [ROOT / "main.py"]:
        rel = path.relative_to(ROOT).as_posix()
        if rel in SKIP_FILES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        excluded = docstring_positions(tree)
        main_ranges = main_block_ranges(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if (node.lineno, node.col_offset) in excluded:
                continue
            if any(start <= node.lineno <= end for start, end in main_ranges):
                continue
            raw = node.value.strip()
            if should_skip_literal(raw):
                continue
            literals[raw] = repair_text(raw)

    for raw in MANUAL_LITERALS:
        literals.setdefault(raw, repair_text(raw))

    return dict(sorted(literals.items(), key=lambda item: item[0]))


def mask(text: str) -> tuple[str, dict[str, str]]:
    replacements: dict[str, str] = {}

    def repl(match: re.Match[str]) -> str:
        token = f"__MASK_{len(replacements)}__"
        replacements[token] = match.group(0)
        return token

    return MASK_RE.sub(repl, text), replacements


def unmask(text: str, replacements: dict[str, str]) -> str:
    for token, original in replacements.items():
        text = text.replace(token, original)
    return text


def chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[i:i + size] for i in range(0, len(values), size)]


def collect_unique_strings(value: Any, out: set[str]) -> None:
    if isinstance(value, str):
        out.add(value)
        return
    if isinstance(value, list):
        for item in value:
            collect_unique_strings(item, out)
        return
    if isinstance(value, dict):
        for item in value.values():
            collect_unique_strings(item, out)


def apply_translations(value: Any, translated: dict[str, str]) -> Any:
    if isinstance(value, str):
        return translated[value]
    if isinstance(value, list):
        return [apply_translations(item, translated) for item in value]
    if isinstance(value, dict):
        return {key: apply_translations(item, translated) for key, item in value.items()}
    return value


def translate_texts(translator: GoogleTranslator, values: set[str]) -> dict[str, str]:
    translated: dict[str, str] = {}
    pending = sorted(values)
    if not pending:
        return translated

    for batch in chunked(pending, 40):
        masked_batch: list[str] = []
        masks: list[dict[str, str]] = []
        for text in batch:
            masked, replacements = mask(text)
            masked_batch.append(masked)
            masks.append(replacements)

        try:
            results = translator.translate_batch(masked_batch)
        except Exception:
            results = [translator.translate(item) for item in masked_batch]

        if isinstance(results, str):
            results = [results]

        for original, replacements, result in zip(batch, masks, results):
            translated[original] = unmask(result, replacements)

    return translated


def build_payload() -> dict[str, Any]:
    payload = repair_value(deepcopy(BASE_LOCALE))
    payload["literals"] = collect_literals()
    return payload


def build_locale(code: str, target_code: str, payload: dict[str, Any]) -> dict[str, Any]:
    if code == "en":
        return deepcopy(payload)

    strings: set[str] = set()
    collect_unique_strings(payload, strings)
    translator = GoogleTranslator(source="en", target=target_code)
    translated = translate_texts(translator, strings)
    return apply_translations(payload, translated)


def main() -> None:
    LOCALES_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()

    def write_locale(code: str, content: dict[str, Any]) -> None:
        path = LOCALES_DIR / f"{code}.json"
        path.write_text(
            json.dumps(content, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Wrote {path}")

    requested = sys.argv[1:]
    if requested:
        codes = [code for code in requested if code == "en" or code in TARGETS]
    else:
        codes = ["en", *TARGETS.keys()]

    if "en" in codes:
        write_locale("en", build_locale("en", "en", payload))

    for code in codes:
        if code == "en":
            continue
        target_code = TARGETS[code]
        print(f"Translating {code}...")
        write_locale(code, build_locale(code, target_code, payload))


if __name__ == "__main__":
    main()
