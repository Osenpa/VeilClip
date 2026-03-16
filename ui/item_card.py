"""
ui/item_card.py
───────────────
Single clipboard history entry card.

Changes vs previous version
────────────────────────────
• Accepts on_copy callback (called after every successful copy so the
  parent window can show a toast notification).
• on_copy is called from all copy paths: left-click, Copy menu, Copy as Plain Text.
"""

import io
import logging
import re
import sys
import weakref
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore    import Qt, pyqtSignal, QMimeData, QPoint, QUrl
from PyQt6.QtGui     import QColor, QCursor, QImage, QPixmap, QAction, QDrag, QIcon
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMenu, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

import utils.i18n as i18n
from utils.config import ICON_APP
from utils.dialogs import prompt_text

logger = logging.getLogger(__name__)


def _apply_window_icon(window) -> None:
    try:
        icon_path = Path(ICON_APP)
        if icon_path.exists():
            window.setWindowIcon(QIcon(str(icon_path)))
    except Exception:
        pass


def _show_non_closing_toast(widget: QWidget, message: str, duration_ms: int = 1800) -> bool:
    parent = widget.parent()
    while parent is not None:
        if hasattr(parent, "_toast"):
            parent._toast.show_message(
                message,
                duration_ms=duration_ms,
                after=None,
                on_undo=None,
            )
            return True
        parent = parent.parent()
    return False

# ── Palette (imported from shared styles) ────────────────────────────────────

from utils.styles import (
    BG_CARD, BG_HOVER, BG_PINNED,
    ACCENT, ACCENT_DIM, TEXT, TEXT_DIM,
    BORDER, BORDER_PIN, RED, RED_DIM,
    btn_primary, btn_ghost, btn_danger,
)

_TYPE_ICON = {"text": "📄", "link": "🔗", "image": "🖼", "filepath": "📁"}
_BROWSER_ICON = {
    "chrome": "🌐", "firefox": "🦊", "edge": "🌀",
    "safari": "🧭", "brave": "🦁", "opera": "🅾", "vivaldi": "🎵",
}

_HEX_RE = re.compile(r"^\s*(#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3}))\s*$")
_RGB_RE = re.compile(
    r"^\s*rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)\s*$", re.I
)

DEFAULT_FAVORITE_CATEGORIES = ("Work", "Personal", "Passwords", "General")
_DEFAULT_CATEGORY_KEYS = {
    "Work": "favorites.categories.work",
    "Personal": "favorites.categories.personal",
    "Passwords": "favorites.categories.passwords",
    "General": "favorites.categories.general",
}

_MENU_STYLE = f"""
QMenu {{
    background:#1A1D27; border:1px solid #2A2D3E; border-radius:8px;
    padding:4px; color:{TEXT}; font-family:'Segoe UI',sans-serif; font-size:12px;
}}
QMenu::item {{ padding:6px 14px; border-radius:5px; }}
QMenu::item:selected {{ background:#6C63FF; color:white; }}
QMenu::item:disabled {{ color:#55586E; }}
QMenu::separator {{ height:1px; background:#2A2D3E; margin:3px 8px; }}
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_color(text: str) -> str | None:
    m = _HEX_RE.match(text)
    if m:
        h = m.group(1)
        return ("#" + "".join(c*2 for c in h[1:])).upper() if len(h)==4 else h.upper()
    m = _RGB_RE.match(text)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if all(0<=v<=255 for v in (r,g,b)):
            return f"#{r:02X}{g:02X}{b:02X}"
    return None


def _browser_icon(source_app: str) -> str:
    name = (source_app or "").lower()
    for k, v in _BROWSER_ICON.items():
        if k in name:
            return v
    return _TYPE_ICON["link"]


def _category_label(category: str) -> str:
    if category in _DEFAULT_CATEGORY_KEYS:
        return i18n.get(_DEFAULT_CATEGORY_KEYS[category])
    return category


# ── Thumbnail cache ───────────────────────────────────────────────────────────
# Maps item_id (int) → QPixmap.  Capped at _THUMB_CACHE_MAX entries (FIFO).

_THUMB_CACHE_MAX = 50
_thumb_cache: dict[int, QPixmap] = {}


def _make_thumbnail(blob: bytes, w=90, h=60) -> QPixmap | None:
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(blob)).convert("RGBA")
        img.thumbnail((w*2, h*2), Image.LANCZOS)
        data = img.tobytes("raw","RGBA")
        qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
        return QPixmap.fromImage(qimg).scaled(w, h,
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    except Exception as exc:
        logger.debug("Thumbnail failed: %s", exc)
        return None


def _get_thumbnail(item_id: int, blob: bytes, w=90, h=60) -> QPixmap | None:
    """Return a cached thumbnail, computing and storing it on first access."""
    if item_id in _thumb_cache:
        return _thumb_cache[item_id]
    pm = _make_thumbnail(blob, w, h)
    if pm is not None:
        # Enforce FIFO size cap
        if len(_thumb_cache) >= _THUMB_CACHE_MAX:
            oldest_key = next(iter(_thumb_cache))
            del _thumb_cache[oldest_key]
        _thumb_cache[item_id] = pm
    return pm


def _fmt_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        d = int((datetime.now(timezone.utc)-dt).total_seconds())
        if d < 60:
            return i18n.get("time.just_now")
        if d < 3600:
            return i18n.get("time.minutes_ago", count=d // 60)
        if d < 86400:
            return i18n.get("time.hours_ago", count=d // 3600)
        return i18n.get("time.days_ago", count=d // 86400)
    except Exception:
        return ""


def _shorten(url: str, n=55) -> str:
    return url if len(url)<=n else url[:n]+"…"


# ── ClipboardItemCard ─────────────────────────────────────────────────────────

class ClipboardItemCard(QWidget):
    clicked          = pyqtSignal(int)
    pin_toggled      = pyqtSignal(int)
    delete_requested = pyqtSignal(int)
    selection_changed = pyqtSignal(int, bool)   # item_id, selected

    _open_editors: weakref.WeakSet = weakref.WeakSet()   # prevent GC of editor windows

    @classmethod
    def _clear_thumb_cache(cls, item_id: int) -> None:
        """Remove a single item's thumbnail from the module-level cache.

        Call this when an image item is deleted so stale pixmaps are freed.
        """
        _thumb_cache.pop(item_id, None)

    def __init__(
        self,
        item: dict,
        on_close: Callable | None = None,
        on_copy:  Callable | None = None,
        on_item_edited: Callable | None = None,
        close_after_copy: bool = True,
        db=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._item             = item
        self._on_close         = on_close
        self._on_copy          = on_copy
        self._on_item_edited   = on_item_edited
        self._close_after_copy = close_after_copy
        self._db               = db
        self._pinned           = bool(item.get("is_pinned", False))
        self._color_hex: str | None = None
        self._type_icon = _TYPE_ICON.get(item["content_type"], "📄")
        self._select_mode      = False   # multi-select mode active
        self._selected         = False   # this card is selected

        self._resolve_hints()
        self._build_ui()
        self._refresh_pin_style()
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setToolTip(i18n.get("item_card.tooltips.click_to_copy"))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    # ── Hints ─────────────────────────────────────────────────────────────────

    def _resolve_hints(self) -> None:
        ct = self._item["content_type"]
        t  = self._item.get("content_text") or ""
        if ct in ("text","link"):
            self._color_hex = _parse_color(t)
        if ct == "link":
            self._type_icon = _browser_icon(self._item.get("source_app") or "")

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        ct = self._item.get("content_type", "text")
        # Image cards are taller to accommodate the bigger thumbnail
        card_h = 80 if ct == "image" else 64
        self.setFixedHeight(card_h)
        self.setContentsMargins(0,0,0,0)
        self._apply_card_style(False)

        root = QHBoxLayout(self)
        root.setContentsMargins(12,8,10,8)
        root.setSpacing(10)

        # Selection indicator (checkbox-like label)
        self._sel_indicator = QLabel("[ ]")
        self._sel_indicator.setFixedSize(22, 22)
        self._sel_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sel_indicator.setStyleSheet(f"color:{TEXT_DIM}; font-size:16px; background:transparent;")
        self._sel_indicator.setVisible(False)
        root.addWidget(self._sel_indicator)

        il = QLabel(self._type_icon)
        il.setFixedSize(28,28)
        il.setAlignment(Qt.AlignmentFlag.AlignCenter)
        il.setStyleSheet("font-size:16px; background:transparent;")
        root.addWidget(il)

        if self._color_hex:
            sw = QPushButton()
            sw.setFixedSize(16,16)
            sw.setToolTip(i18n.get("item_card.tooltips.copy_color", value=self._color_hex))
            sw.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            sw.setStyleSheet(f"QPushButton{{background:{self._color_hex}; border:1px solid rgba(255,255,255,.25); border-radius:3px;}} QPushButton:hover{{border:1px solid white;}}")
            sw.clicked.connect(lambda _, h=self._color_hex: self._copy_hex(h))
            root.addWidget(sw)

        root.addLayout(self._make_preview(), stretch=1)

        self._pin_btn = QPushButton("📌")
        self._pin_btn.setFixedSize(30,30)
        self._pin_btn.setToolTip(i18n.get("item_card.tooltips.pin_toggle"))
        self._pin_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._pin_btn.clicked.connect(self._handle_pin)
        root.addWidget(self._pin_btn)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(30,30)
        del_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        del_btn.setStyleSheet(f"QPushButton{{background:{RED_DIM}; color:#FFB3B3; border:1px solid {RED}; border-radius:7px; font-size:11px; font-weight:700;}} QPushButton:hover{{background:{RED}; color:white;}}")
        del_btn.clicked.connect(self._handle_delete)
        root.addWidget(del_btn)

    def _make_preview(self) -> QVBoxLayout:
        lay = QVBoxLayout()
        lay.setContentsMargins(0,0,0,0)
        lay.setSpacing(2)
        ct = self._item["content_type"]

        if ct == "image" and self._item.get("content_blob"):
            thumb = _get_thumbnail(self._item["id"], self._item["content_blob"])
            if thumb:
                tl = QLabel(); tl.setPixmap(thumb); tl.setFixedSize(90,60)
                tl.setStyleSheet("border-radius:4px; border:1px solid rgba(255,255,255,.1); background:transparent;")
                row = QHBoxLayout(); row.setContentsMargins(0,0,0,0)
                row.addWidget(tl); row.addStretch()
                lay.addLayout(row)
            else:
                lay.addWidget(self._mlabel(i18n.get("item_card.preview.image")))
        else:
            raw = self._item.get("content_text") or ""
            if ct == "link":
                prev = _shorten(raw)
            else:
                flat = " ".join(raw.split())   # collapse all whitespace
                prev = flat[:50] + "…" if len(flat) > 52 else flat
            lbl = self._mlabel(prev)
            if self._color_hex:
                lbl.setStyleSheet(f"color:{self._color_hex}; font-family:'Consolas',monospace; font-size:12px; font-weight:700; background:transparent;")
            lay.addWidget(lbl)

        src = self._item.get("source_app") or i18n.get("common.unknown")
        ts  = _fmt_time(self._item.get("created_at",""))

        # Build bottom row: source·time on left, char/word count on right (text items only)
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0,0,0,0)
        bottom_row.setSpacing(0)

        sub = QLabel(f"{src}  ·  {ts}" if ts else src)
        sub.setStyleSheet(f"color:{TEXT_DIM}; font-family:'Segoe UI',sans-serif; font-size:10px; background:transparent;")
        sub.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bottom_row.addWidget(sub, stretch=1)

        ct = self._item["content_type"]
        if ct in ("text", "link"):
            raw = self._item.get("content_text") or ""
            if raw.strip():
                chars = len(raw)
                words = len(raw.split())
                count_lbl = QLabel(i18n.get("item_card.counts", chars=chars, words=words))
                count_lbl.setStyleSheet(
                    f"color:{TEXT_DIM}; font-family:'Consolas',monospace; "
                    f"font-size:9px; background:transparent;"
                )
                count_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                bottom_row.addWidget(count_lbl)

        lay.addLayout(bottom_row)
        return lay

    def _mlabel(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{TEXT}; font-family:'Segoe UI',sans-serif; font-size:12px; background:transparent;")
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lbl.setWordWrap(False)
        return lbl

    # ── Style ─────────────────────────────────────────────────────────────────

    def _apply_card_style(self, hovered: bool) -> None:
        if self._selected:
            self.setStyleSheet(f"ClipboardItemCard{{background:#1E2A4A; border:2px solid {ACCENT}; border-radius:10px;}}")
        else:
            bg, border = (
                (BG_PINNED, BORDER_PIN) if self._pinned else
                (BG_HOVER,  ACCENT_DIM) if hovered     else
                (BG_CARD,   BORDER)
            )
            self.setStyleSheet(f"ClipboardItemCard{{background:{bg}; border:1px solid {border}; border-radius:10px;}}") 

    # ── Select mode ───────────────────────────────────────────────────────────

    def set_select_mode(self, enabled: bool) -> None:
        """Toggle multi-select mode. Shows/hides checkbox, disables copy-on-click."""
        self._select_mode = enabled
        if not enabled:
            self._selected = False
        self._apply_card_style(False)
        # Show/hide the select indicator
        if hasattr(self, "_sel_indicator"):
            self._sel_indicator.setVisible(enabled)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._apply_card_style(False)
        if hasattr(self, "_sel_indicator"):
            self._sel_indicator.setText("[x]" if selected else "[ ]")
            self._sel_indicator.setStyleSheet(
                f"color:{ACCENT}; font-size:16px; background:transparent;" if selected
                else f"color:{TEXT_DIM}; font-size:16px; background:transparent;"
            )

    def is_selected(self) -> bool:
        return self._selected

    def _refresh_pin_style(self) -> None:
        if self._pinned:
            self._pin_btn.setStyleSheet(f"QPushButton{{background:{ACCENT}; border:none; border-radius:7px; font-size:14px;}} QPushButton:hover{{background:#7D75FF;}}")
        else:
            self._pin_btn.setStyleSheet(f"QPushButton{{background:transparent; border:1px solid {BORDER}; border-radius:7px; color:{TEXT_DIM}; font-size:14px;}} QPushButton:hover{{background:{BG_HOVER}; border-color:{ACCENT_DIM};}}")

    # ── Context menu ──────────────────────────────────────────────────────────

    def _show_context_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(_MENU_STYLE)
        ct = self._item["content_type"]

        a = QAction("📋  Copy", self);        a.triggered.connect(self._handle_click);       menu.addAction(a)
        a = QAction("📝  Copy as Plain Text", self); a.setEnabled(ct != "image"); a.triggered.connect(self._handle_copy_plain); menu.addAction(a)
        a = QAction("✏️  Edit Text", self);   a.setEnabled(ct != "image"); a.triggered.connect(self._handle_edit_text); menu.addAction(a)
        a = QAction("🖼  Edit Image", self);  a.setEnabled(ct=="image" and bool(self._item.get("content_blob"))); a.triggered.connect(self._handle_edit_image); menu.addAction(a)
        menu.addSeparator()
        a = QAction("📌  Unpin" if self._pinned else "📌  Pin", self); a.triggered.connect(self._handle_pin); menu.addAction(a)

        # Favorites submenu — shows which categories this item is already in
        if self._db:
            # Find which categories already contain this item
            existing_favs = self._db.get_favorites()
            item_id = self._item["id"]
            in_categories = {
                f["category"] for f in existing_favs if f.get("item_id") == item_id
            }

            fav_menu = menu.addMenu("Add to Favorites")
            fav_menu.setStyleSheet(_MENU_STYLE)
            default_cats = ["Work", "Personal", "Passwords", "General"]
            categories   = self._db.get_favorite_categories()
            all_cats = list(dict.fromkeys(default_cats + categories))

            for cat in all_cats:
                if cat in in_categories:
                    # Already saved — show it grayed out with a note
                    a = QAction(i18n.get("favorites.category_saved", category=_category_label(cat)), self)
                    a.setEnabled(False)
                else:
                    a = QAction(cat, self)
                    a.triggered.connect(lambda _, c=cat: self._add_to_favorites(c))
                fav_menu.addAction(a)

            fav_menu.addSeparator()
            a = QAction("+ New Category…", self)
            a.triggered.connect(self._add_to_favorites_new_category)
            fav_menu.addAction(a)

        menu.addSeparator()
        a = QAction("🗑  Delete", self);      a.triggered.connect(self._handle_delete);      menu.addAction(a)
        menu.exec(self.mapToGlobal(pos))

    # ── Mouse ─────────────────────────────────────────────────────────────────

    def enterEvent(self, e) -> None: self._apply_card_style(True);  super().enterEvent(e)
    def leaveEvent(self, e) -> None: self._apply_card_style(False); super().leaveEvent(e)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
        if not hasattr(self, "_drag_start_pos"):
            super().mouseMoveEvent(event)
            return
        dist = (event.pos() - self._drag_start_pos).manhattanLength()
        if dist < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return
        self._start_drag()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            dist = 0
            if hasattr(self, "_drag_start_pos"):
                dist = (event.pos() - self._drag_start_pos).manhattanLength()
            if dist < QApplication.startDragDistance():
                if self._select_mode:
                    # In select mode: toggle selection instead of copy
                    self._selected = not self._selected
                    self.set_selected(self._selected)
                    self.selection_changed.emit(self._item["id"], self._selected)
                else:
                    child = self.childAt(event.pos())
                    if child is None or not isinstance(child, QPushButton):
                        self._handle_click()
        super().mouseReleaseEvent(event)

    def _start_drag(self) -> None:
        """Initiate a drag operation for this clipboard item."""
        mime = QMimeData()
        ct   = self._item.get("content_type", "text")

        if ct == "image" and self._item.get("content_blob"):
            try:
                blob = self._item["content_blob"]
                import io
                from PIL import Image
                img  = Image.open(io.BytesIO(blob)).convert("RGBA")
                data = img.tobytes("raw", "RGBA")
                qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
                mime.setImageData(qimg)
                # Write to a temp file so dragging to desktop/explorer works.
                # The file is deleted after the drag operation completes.
                import tempfile, os
                tmp = tempfile.NamedTemporaryFile(
                    suffix=".png", delete=False, prefix="veilclip_"
                )
                tmp.close()
                img.save(tmp.name, "PNG")
                mime.setUrls([QUrl.fromLocalFile(tmp.name)])
                self._drag_tmp_path = tmp.name   # remember for cleanup
            except Exception as exc:
                logger.debug("Drag image prep failed: %s", exc)
                return
        else:
            text = self._item.get("content_text") or ""
            mime.setText(text)
            # If it looks like a URL, also expose as URL list
            stripped = text.strip()
            if stripped.startswith(("http://", "https://", "ftp://")):
                mime.setUrls([QUrl(stripped)])

        drag = QDrag(self)
        drag.setMimeData(mime)

        # Build a small drag pixmap from the card
        pm = self.grab().scaled(
            300, 60,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        drag.setPixmap(pm)
        drag.setHotSpot(QPoint(pm.width() // 2, pm.height() // 2))

        drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)

        # Clean up temp image file created for desktop drop
        tmp_path = getattr(self, "_drag_tmp_path", None)
        if tmp_path:
            try:
                import os
                os.unlink(tmp_path)
            except Exception:
                pass
            self._drag_tmp_path = None

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _handle_click(self) -> None:
        ct = self._item["content_type"]
        try:
            if ct == "image" and self._item.get("content_blob"):
                self._copy_image_to_clipboard(self._item["content_blob"])
            else:
                QApplication.clipboard().setText(self._item.get("content_text") or "")
            logger.debug("Copied item id=%s.", self._item["id"])
            if self._on_copy:
                # on_copy is show_copy_toast in main_window, which handles
                # close-after-copy timing via the toast callback
                self._on_copy(i18n.get("notifications.copied"))
        except Exception as exc:
            logger.error("Copy failed: %s", exc)
        self.clicked.emit(self._item["id"])

    def _handle_copy_plain(self) -> None:
        try:
            from utils.text_cleaner import strip_formatting, is_rich_text
            raw   = self._item.get("content_text") or ""
            clean = strip_formatting(raw) if is_rich_text(raw) else raw
            QApplication.clipboard().setText(clean)
            if self._on_copy:
                self._on_copy(i18n.get("notifications.copied_plain"))
        except Exception as exc:
            logger.error("Copy-plain failed: %s", exc)

    def _handle_pin(self) -> None:
        self._pinned = not self._pinned
        self._refresh_pin_style()
        self._apply_card_style(False)
        self.pin_toggled.emit(self._item["id"])

    def _handle_delete(self) -> None:
        self.delete_requested.emit(self._item["id"])

    def _handle_edit_text(self) -> None:
        """Open a simple text editor dialog for the clipboard item."""
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QPlainTextEdit, QVBoxLayout, QLabel
        current = self._item.get("content_text") or ""

        dlg = QDialog(self)
        dlg.setWindowTitle(i18n.get("item_card.edit_title"))
        _apply_window_icon(dlg)
        dlg.setMinimumSize(460, 300)
        dlg.setStyleSheet(f"""
            QDialog {{ background:#1A1D27; color:#E8E8F0;
                      font-family:'Segoe UI',sans-serif; }}
            QLabel  {{ background:transparent; color:#7B7D8E; font-size:11px; }}
            QPlainTextEdit {{
                background:#0F1117; color:#E8E8F0;
                border:1px solid #2A2D3E; border-radius:8px;
                font-family:'Segoe UI',sans-serif; font-size:12px;
                selection-background-color:#6C63FF;
                padding:6px;
            }}
            QPushButton {{
                background:#6C63FF; color:white; border:none;
                border-radius:7px; font-size:12px; font-weight:700;
                padding:6px 20px;
            }}
            QPushButton:hover {{ background:#7D75FF; }}
            QPushButton[text="Cancel"] {{
                background:#22263A; color:#7B7D8E;
                border:1px solid #2A2D3E;
            }}
            QPushButton[text="Cancel"]:hover {{ background:#2A2D3E; color:#E8E8F0; }}
        """)

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        hint = QLabel(i18n.get("item_card.edit_hint"))
        lay.addWidget(hint)

        editor = QPlainTextEdit()
        editor.setPlainText(current)
        lay.addWidget(editor, stretch=1)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(i18n.get("common.ok"))
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText(i18n.get("common.cancel"))
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_text = editor.toPlainText()
            if self._db:
                try:
                    self._db.update_text(self._item["id"], new_text)
                    self._item["content_text"] = new_text
                    # Rebuild this card's preview in-place immediately
                    self._rebuild_preview()
                    self.update()
                    QApplication.clipboard().setText(new_text)
                    # Schedule full panel refresh for AFTER the dialog is gone.
                    # Using QTimer(0) ensures the event loop has returned from
                    # dlg.exec() before we touch the parent widget tree.
                    _cb_edited   = self._on_item_edited
                    _cb_copy     = self._on_copy
                    _close_orig  = self._close_after_copy
                    def _post_edit():
                        if _cb_edited:
                            _cb_edited()
                        if _cb_copy:
                            self._close_after_copy = False
                            _cb_copy(i18n.get("notifications.text_updated"))
                            self._close_after_copy = _close_orig
                    from PyQt6.QtCore import QTimer as _QT
                    _QT.singleShot(0, _post_edit)
                except Exception as exc:
                    logger.error("Edit text failed: %s", exc)

    def _rebuild_preview(self) -> None:
        """Destroy and recreate the preview section of the card in-place."""
        # The preview layout is the stretch-1 item in the root HBoxLayout
        root_layout = self.layout()
        if root_layout is None:
            return
        # Find and remove old preview layout (index 1 if no color swatch, 2 if swatch)
        for i in range(root_layout.count()):
            item = root_layout.itemAt(i)
            if item and item.layout() and item.stretch() == 1:
                # Remove all widgets inside this layout
                old_lay = item.layout()
                while old_lay.count():
                    child = old_lay.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                # Insert new preview content into the same layout
                new_lay = self._make_preview()
                while new_lay.count():
                    child = new_lay.takeAt(0)
                    if child.widget():
                        old_lay.addWidget(child.widget())

    def _copy_hex(self, h: str) -> None:
        QApplication.clipboard().setText(h)
        if self._on_copy:
            self._on_copy(i18n.get("notifications.copied_value", value=h))

    def _handle_edit_image(self) -> None:
        blob = self._item.get("content_blob")
        if not blob:
            return
        try:
            from ui.image_editor import ImageEditorWindow
            ed = ImageEditorWindow(bytes(blob))
            ed.show()
            ClipboardItemCard._open_editors.add(ed)
        except Exception as exc:
            logger.error("Image editor failed: %s", exc)

    def _add_to_favorites(self, category: str) -> None:
        if not self._db:
            return
        result = self._db.add_favorite(self._item, category)
        if result is not None:
            # Show a brief toast without triggering the close-after-copy behaviour.
            # We reach into the parent window's toast directly so we bypass
            # show_copy_toast (which schedules a window close).
            try:
                parent = self.parent()
                while parent is not None:
                    if hasattr(parent, "_toast") and hasattr(parent, "_close_after_copy"):
                        parent._toast.show_message(
                            i18n.get("favorites.saved_to", category=_category_label(category)),
                            duration_ms=1800,
                            after=None,
                            on_undo=None,
                        )
                        return
                    parent = parent.parent()
            except Exception:
                pass
            # Fallback: call on_copy but temporarily disable close-after-copy
            if self._on_copy:
                orig = self._close_after_copy
                self._close_after_copy = False
                self._on_copy(i18n.get("favorites.saved_to", category=_category_label(category)))
                self._close_after_copy = orig

    def _add_to_favorites_new_category(self) -> None:
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, "New Category", "Category name:",
        )
        if ok and name.strip():
            self._add_to_favorites(name.strip())

    @staticmethod
    def _copy_image_to_clipboard(blob: bytes) -> None:
        from PIL import Image
        img  = Image.open(io.BytesIO(blob)).convert("RGBA")
        data = img.tobytes("raw","RGBA")
        qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
        QApplication.clipboard().setPixmap(QPixmap.fromImage(qimg))

    @property
    def item_id(self) -> int:
        return self._item["id"]


class FavoriteItemCard(QWidget):
    removed = pyqtSignal(int)

    def __init__(
        self,
        favorite: dict,
        db=None,
        on_copy: Callable | None = None,
        on_item_edited: Callable | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._favorite = favorite
        self._db = db
        self._on_copy = on_copy
        self._on_item_edited = on_item_edited
        self._drag_start_pos = QPoint()
        self._build_ui()
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setToolTip(i18n.get("item_card.tooltips.click_to_copy"))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _build_ui(self) -> None:
        ct = self._favorite.get("content_type", "text")
        is_image = ct == "image"
        card_h = 80 if is_image else 64

        self.setFixedHeight(card_h)
        self.setContentsMargins(0, 0, 0, 0)
        self._apply_card_style(False)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 8, 10, 8)
        root.setSpacing(10)

        if is_image and self._favorite.get("content_blob"):
            thumb = _get_thumbnail(self._favorite["id"], self._favorite["content_blob"], w=72, h=56)
            if thumb:
                tl = QLabel()
                tl.setPixmap(thumb)
                tl.setFixedSize(72, 56)
                tl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                tl.setStyleSheet(
                    "border-radius:5px; border:1px solid rgba(255,255,255,.12); background:transparent;"
                )
                root.addWidget(tl)
            else:
                il = QLabel(_TYPE_ICON["image"])
                il.setFixedSize(28, 28)
                il.setAlignment(Qt.AlignmentFlag.AlignCenter)
                il.setStyleSheet("font-size:16px; background:transparent;")
                root.addWidget(il)
        else:
            type_icon = _TYPE_ICON.get(ct, _TYPE_ICON["text"])
            il = QLabel(type_icon)
            il.setFixedSize(28, 28)
            il.setAlignment(Qt.AlignmentFlag.AlignCenter)
            il.setStyleSheet("font-size:16px; background:transparent;")
            root.addWidget(il)

        v = QVBoxLayout()
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)

        raw = self._favorite.get("content_text") or ""
        flat = " ".join(raw.split())
        if is_image and not flat:
            preview = i18n.get("item_card.preview.image")
        else:
            preview = flat[:52] + "…" if len(flat) > 54 else flat

        self._preview_lbl = QLabel(preview)
        self._preview_lbl.setStyleSheet(
            f"color:{TEXT}; font-family:'Segoe UI',sans-serif; font-size:12px; background:transparent;"
        )
        v.addWidget(self._preview_lbl)

        self._cat_lbl = QLabel(_category_label(self._favorite.get("category", "General")))
        self._cat_lbl.setStyleSheet(
            f"color:{ACCENT}; font-family:'Segoe UI',sans-serif; font-size:10px; background:transparent;"
        )
        v.addWidget(self._cat_lbl)
        root.addLayout(v, stretch=1)

        copy_btn = QPushButton(i18n.get("common.copy"))
        copy_btn.setFixedHeight(26)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT_DIM}; color:{TEXT}; border:none; border-radius:6px;
                          font-family:'Segoe UI',sans-serif; font-size:10px; padding:0 8px; }}
            QPushButton:hover {{ background:{ACCENT}; color:white; }}
        """)
        copy_btn.clicked.connect(self._handle_click)
        root.addWidget(copy_btn)

        rem_btn = QPushButton("✕")
        rem_btn.setFixedSize(28, 28)
        rem_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        rem_btn.setStyleSheet(f"""
            QPushButton {{ background:{RED_DIM}; color:#FFB3B3; border:1px solid {RED};
                          border-radius:6px; font-size:11px; font-weight:700; }}
            QPushButton:hover {{ background:{RED}; color:white; }}
        """)
        rem_btn.clicked.connect(self._handle_remove)
        root.addWidget(rem_btn)

    def _show_context_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(_MENU_STYLE)
        ct = self._favorite.get("content_type", "text")

        a = QAction("📋  Copy", self)
        a.triggered.connect(self._handle_click)
        menu.addAction(a)

        a = QAction("📝  Copy as Plain Text", self)
        a.setEnabled(ct != "image")
        a.triggered.connect(self._handle_copy_plain)
        menu.addAction(a)

        a = QAction("✏️  Edit Text", self)
        a.setEnabled(ct != "image")
        a.triggered.connect(self._handle_edit_text)
        menu.addAction(a)

        a = QAction("🖼  Edit Image", self)
        a.setEnabled(ct == "image" and bool(self._favorite.get("content_blob")))
        a.triggered.connect(self._handle_edit_image)
        menu.addAction(a)

        menu.addSeparator()
        a = QAction("🗑  Delete", self)
        a.triggered.connect(self._handle_remove)
        menu.addAction(a)
        menu.exec(self.mapToGlobal(pos))

    def _apply_card_style(self, hovered: bool) -> None:
        bg = BG_HOVER if hovered else BG_CARD
        self.setStyleSheet(f"background:{bg}; border:1px solid {BORDER}; border-radius:10px;")

    def enterEvent(self, event) -> None:
        self._apply_card_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._apply_card_style(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
        dist = (event.pos() - self._drag_start_pos).manhattanLength()
        if dist < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return
        self._start_drag()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            dist = (event.pos() - self._drag_start_pos).manhattanLength()
            if dist < QApplication.startDragDistance():
                child = self.childAt(event.pos())
                if child is None or not isinstance(child, QPushButton):
                    self._handle_click()
        super().mouseReleaseEvent(event)

    def _handle_click(self) -> None:
        ct = self._favorite.get("content_type", "text")
        try:
            if ct == "image" and self._favorite.get("content_blob"):
                ClipboardItemCard._copy_image_to_clipboard(self._favorite["content_blob"])
                message = i18n.get("notifications.image_copied")
            else:
                QApplication.clipboard().setText(self._favorite.get("content_text") or "")
                message = i18n.get("notifications.copied")
            if self._on_copy:
                self._on_copy(message)
        except Exception as exc:
            logger.error("Favorite copy failed: %s", exc)

    def _handle_copy_plain(self) -> None:
        try:
            from utils.text_cleaner import strip_formatting, is_rich_text

            raw = self._favorite.get("content_text") or ""
            clean = strip_formatting(raw) if is_rich_text(raw) else raw
            QApplication.clipboard().setText(clean)
            if self._on_copy:
                self._on_copy(i18n.get("notifications.copied_plain"))
        except Exception as exc:
            logger.error("Favorite copy-plain failed: %s", exc)

    def _handle_edit_text(self) -> None:
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QPlainTextEdit, QVBoxLayout, QLabel

        current = self._favorite.get("content_text") or ""
        dlg = QDialog(self)
        dlg.setWindowTitle(i18n.get("item_card.edit_title"))
        _apply_window_icon(dlg)
        dlg.setMinimumSize(460, 300)
        dlg.setStyleSheet(f"""
            QDialog {{ background:#1A1D27; color:#E8E8F0;
                      font-family:'Segoe UI',sans-serif; }}
            QLabel  {{ background:transparent; color:#7B7D8E; font-size:11px; }}
            QPlainTextEdit {{
                background:#0F1117; color:#E8E8F0;
                border:1px solid #2A2D3E; border-radius:8px;
                font-family:'Segoe UI',sans-serif; font-size:12px;
                selection-background-color:#6C63FF;
                padding:6px;
            }}
            QPushButton {{
                background:#6C63FF; color:white; border:none;
                border-radius:7px; font-size:12px; font-weight:700;
                padding:6px 20px;
            }}
            QPushButton:hover {{ background:#7D75FF; }}
            QPushButton[text="Cancel"] {{
                background:#22263A; color:#7B7D8E;
                border:1px solid #2A2D3E;
            }}
            QPushButton[text="Cancel"]:hover {{ background:#2A2D3E; color:#E8E8F0; }}
        """)

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        hint = QLabel(i18n.get("item_card.edit_hint"))
        lay.addWidget(hint)

        editor = QPlainTextEdit()
        editor.setPlainText(current)
        lay.addWidget(editor, stretch=1)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(i18n.get("common.ok"))
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText(i18n.get("common.cancel"))
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec() == QDialog.DialogCode.Accepted and self._db:
            new_text = editor.toPlainText()
            try:
                if self._db.update_favorite_text(self._favorite["id"], new_text):
                    self._favorite["content_text"] = new_text
                    self._refresh_preview()
                    QApplication.clipboard().setText(new_text)
                    _show_non_closing_toast(self, i18n.get("notifications.text_updated"))
                    if self._on_item_edited:
                        from PyQt6.QtCore import QTimer as _QT
                        _QT.singleShot(0, self._on_item_edited)
            except Exception as exc:
                logger.error("Favorite edit text failed: %s", exc)

    def _handle_edit_image(self) -> None:
        blob = self._favorite.get("content_blob")
        if not blob:
            return
        try:
            from ui.image_editor import ImageEditorWindow

            ed = ImageEditorWindow(bytes(blob))
            ed.show()
            ClipboardItemCard._open_editors.add(ed)
        except Exception as exc:
            logger.error("Favorite image editor failed: %s", exc)

    def _handle_remove(self) -> None:
        self.removed.emit(self._favorite["id"])

    def _refresh_preview(self) -> None:
        raw = self._favorite.get("content_text") or ""
        flat = " ".join(raw.split())
        if self._favorite.get("content_type") == "image" and not flat:
            preview = i18n.get("item_card.preview.image")
        else:
            preview = flat[:52] + "…" if len(flat) > 54 else flat
        self._preview_lbl.setText(preview)
        self.update()

    def _start_drag(self) -> None:
        mime = QMimeData()
        ct = self._favorite.get("content_type", "text")

        if ct == "image" and self._favorite.get("content_blob"):
            try:
                blob = self._favorite["content_blob"]
                from PIL import Image
                img = Image.open(io.BytesIO(blob)).convert("RGBA")
                data = img.tobytes("raw", "RGBA")
                qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
                mime.setImageData(qimg)

                import tempfile

                tmp = tempfile.NamedTemporaryFile(
                    suffix=".png", delete=False, prefix="veilclip_favorite_"
                )
                tmp.close()
                img.save(tmp.name, "PNG")
                mime.setUrls([QUrl.fromLocalFile(tmp.name)])
                self._drag_tmp_path = tmp.name
            except Exception as exc:
                logger.debug("Favorite drag image prep failed: %s", exc)
                return
        else:
            text = self._favorite.get("content_text") or ""
            mime.setText(text)
            stripped = text.strip()
            if stripped.startswith(("http://", "https://", "ftp://")):
                mime.setUrls([QUrl(stripped)])

        drag = QDrag(self)
        drag.setMimeData(mime)
        pm = self.grab().scaled(
            300, 60,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        drag.setPixmap(pm)
        drag.setHotSpot(QPoint(pm.width() // 2, pm.height() // 2))
        drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)

        tmp_path = getattr(self, "_drag_tmp_path", None)
        if tmp_path:
            try:
                import os
                os.unlink(tmp_path)
            except Exception:
                pass
            self._drag_tmp_path = None
