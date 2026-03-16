"""
ui/main_window.py
─────────────────
VeilClip main popup window.

Changes vs previous version
────────────────────────────
#1  Instant update  — notify_new_item always refreshes (not only when visible)
#2  Bigger default  — 460 × 560 px default, max 80 % screen height
#3  Resizable       — user can drag the bottom-right corner to resize;
                      size is remembered across sessions
#4  Copy toast      — a brief "✓ Copied!" banner fades in/out after copying
#5  Position memory — first open → cursor position; subsequent opens →
                      last known position.  Behaviour toggled in settings.
"""

import logging
import sys
from collections import defaultdict
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore    import Qt, QEvent, QObject, QPoint, QTimer
from PyQt6.QtGui     import QColor, QCursor, QIcon, QKeyEvent, QPainter, QPaintEvent, QResizeEvent
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSizeGrip, QVBoxLayout, QWidget,
)

import utils.i18n as i18n
from utils.config import ICON_APP
from utils.config_manager import cfg as _cfg
from utils.hotkey import get_cursor_position
from utils.dialogs import confirm
from utils.styles import (
    BG, BG_CARD, BG_HOVER, BG_GROUP, BG_PINNED,
    ACCENT, ACCENT_DIM, TEXT, TEXT_DIM, TEXT_GROUP,
    BORDER, RED, RED_DIM,
    btn_primary, btn_ghost, btn_danger, btn_icon, scrollbar_style,
)
from ui.item_card import ClipboardItemCard, FavoriteItemCard, DEFAULT_FAVORITE_CATEGORIES, _category_label

logger = logging.getLogger(__name__)

# ── Default geometry ──────────────────────────────────────────────────────────

DEFAULT_W = 700
DEFAULT_H = 660
MIN_W     = 640
MIN_H     = 480


# ── Acrylic blur ──────────────────────────────────────────────────────────────

def _apply_acrylic(hwnd: int) -> bool:
    try:
        import ctypes, ctypes.wintypes

        class _AP(ctypes.Structure):
            _fields_ = [("AccentState", ctypes.c_uint), ("AccentFlags", ctypes.c_uint),
                        ("GradientColor", ctypes.c_uint), ("AnimationId", ctypes.c_uint)]

        class _WCA(ctypes.Structure):
            _fields_ = [("Attribute", ctypes.c_int), ("pData", ctypes.c_void_p),
                        ("ulDataSize", ctypes.c_ulong)]

        accent               = _AP()
        accent.AccentState   = 4
        accent.GradientColor = 0xCC0F1117
        data            = _WCA()
        data.Attribute  = 19
        data.pData      = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
        data.ulDataSize = ctypes.sizeof(accent)
        fn = ctypes.windll.user32.SetWindowCompositionAttribute
        fn.restype  = ctypes.c_bool
        fn.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(_WCA)]
        return bool(fn(hwnd, ctypes.byref(data)))
    except Exception as exc:
        logger.debug("Acrylic unavailable: %s", exc)
        return False


# ── Filter helper ─────────────────────────────────────────────────────────────

def _matches(item: dict, query: str) -> bool:
    q = query.lower()
    return (
        q in (item.get("content_text") or "").lower() or
        q in (item.get("source_app")   or "").lower()
    )


def _matches_favorite(item: dict, query: str) -> bool:
    q = query.lower()
    return (
        q in (item.get("content_text") or "").lower() or
        q in (item.get("source_app") or "").lower() or
        q in (item.get("category") or "").lower()
    )


# ── Group header ──────────────────────────────────────────────────────────────

class _GroupHeader(QWidget):
    def __init__(self, label: str, count: int, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setStyleSheet(f"background:{BG_GROUP}; border-radius:6px; border:1px solid {BORDER};")
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 0, 10, 0)
        h.setSpacing(6)
        for stretch in (True, False, True):
            if stretch:
                sep = QWidget(); sep.setFixedHeight(1)
                sep.setStyleSheet(f"background:{BORDER}; border:none;")
                h.addWidget(sep, stretch=1)
            else:
                lbl = QLabel(f"{i18n.literal(label)}  ({count})")
                lbl.setStyleSheet(f"color:{TEXT_GROUP}; font-family:'Segoe UI',sans-serif; "
                                  f"font-size:10px; font-weight:600; background:transparent;")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                h.addWidget(lbl)


# ── Toast notification ────────────────────────────────────────────────────────

class _Toast(QWidget):
    """Brief overlay toast that fades out automatically.

    Optionally shows an 'Undo' button (for delete operations).
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"""
            QWidget {{
                background: {ACCENT};
                border-radius: 8px;
            }}
        """)
        self.hide()

        h = QHBoxLayout(self)
        h.setContentsMargins(14, 6, 10, 6)
        h.setSpacing(10)

        self._label = QLabel()
        self._label.setStyleSheet(
            "color: white; font-family: 'Segoe UI', sans-serif;"
            "font-size: 12px; font-weight: 700; background: transparent;"
        )
        self._label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(self._label, stretch=1)

        self._undo_btn = QPushButton("Undo")
        self._undo_btn.setFixedHeight(22)
        self._undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._undo_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.22);
                color: white;
                border: 1px solid rgba(255,255,255,0.45);
                border-radius: 5px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 10px;
                font-weight: 700;
                padding: 0 8px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.35); }
        """)
        self._undo_btn.hide()
        self._undo_btn.clicked.connect(self._on_undo_clicked)
        h.addWidget(self._undo_btn)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timer)

        self._after_cb = None
        self._after_timer = QTimer(self)
        self._after_timer.setSingleShot(True)
        self._after_timer.timeout.connect(self._fire_after)

        self._on_undo_cb = None

    def _on_timer(self) -> None:
        self._on_undo_cb = None   # undo window has passed — discard callback
        self.hide()

    def _fire_after(self) -> None:
        if self._after_cb:
            cb = self._after_cb
            self._after_cb = None
            cb()

    def _on_undo_clicked(self) -> None:
        self._timer.stop()
        self._after_timer.stop()
        cb = self._on_undo_cb
        self._on_undo_cb = None
        self._after_cb = None
        self.hide()
        if cb:
            cb()

    def show_message(
        self,
        msg: str = "✓ Copied!",
        duration_ms: int = 600,
        after: "callable | None" = None,
        undo_label: str = "Undo",
        on_undo: "callable | None" = None,
    ) -> None:
        """Show the toast.

        Parameters
        ----------
        msg          Text to display.
        duration_ms  How long the toast stays visible (ms).
        after        Called ~80 ms after the toast hides (e.g. close window).
        undo_label   Label text for the undo button (shown only if on_undo set).
        on_undo      If provided, an Undo button is shown; called when clicked.
        """
        self._after_timer.stop()
        self._after_cb  = after
        self._on_undo_cb = on_undo

        self._label.setText(msg)

        if on_undo:
            self._undo_btn.setText(undo_label)
            self._undo_btn.show()
        else:
            self._undo_btn.hide()

        self.adjustSize()
        pw = self.parent().width()
        self.move((pw - self.width()) // 2, 56)
        self.show()
        self.raise_()
        self._timer.start(duration_ms)
        if after:
            self._after_timer.start(duration_ms + 80)


# ── Outside-click filter ─────────────────────────────────────────────────────

class _OutsideClickFilter(QObject):
    """Native WH_MOUSE_LL hook that closes the panel on clicks outside it.

    The hook runs in a background thread.  We use QMetaObject.invokeMethod
    with AutoConnection so _check() always executes on the Qt main thread —
    this is the only thread-safe way to touch Qt widgets from a foreign thread.
    """

    # Qt slot so invokeMethod can target it safely
    from PyQt6.QtCore import pyqtSlot

    def __init__(self, panel: "VeilClipWindow") -> None:
        super().__init__(panel)
        self._panel = panel
        self._hook  = None

    # ── Called from hook background thread ───────────────────────────────────

    def _on_click(self) -> None:
        """Scheduled from the hook thread; routes _check to the main thread."""
        from PyQt6.QtCore import QMetaObject, Qt as _Qt
        QMetaObject.invokeMethod(self, "_check", _Qt.ConnectionType.QueuedConnection)

    # ── Runs on Qt main thread (via invokeMethod) ────────────────────────────

    @pyqtSlot()
    def _check(self) -> None:
        panel = self._panel
        if not panel._close_on_outside_click or not panel.isVisible():
            return
        try:
            import ctypes, ctypes.wintypes
            pt = ctypes.wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            gpos = QPoint(pt.x, pt.y)
        except Exception:
            return
        if panel.geometry().contains(gpos):
            return
        siblings = list(panel._sibling_windows)
        try:
            from ui.item_card import ClipboardItemCard
            siblings.extend(list(ClipboardItemCard._open_editors))
        except Exception:
            pass
        for s in siblings:
            try:
                if s is not None and s.isVisible() and s.geometry().contains(gpos):
                    return
            except Exception:
                pass
        panel.hide_window()

    # ── Hook lifecycle ───────────────────────────────────────────────────────

    def install(self) -> None:
        if self._hook:
            return
        try:
            from utils.win_mouse_hook import WinMouseHook
            self._hook = WinMouseHook(callback=self._on_click)
            self._hook.start()
            logger.debug("_OutsideClickFilter: hook installed")
        except Exception as exc:
            logger.warning("_OutsideClickFilter.install failed: %s", exc)

    def uninstall(self) -> None:
        if not self._hook:
            return
        try:
            self._hook.stop()
            self._hook = None
            logger.debug("_OutsideClickFilter: hook uninstalled")
        except Exception as exc:
            logger.warning("_OutsideClickFilter.uninstall failed: %s", exc)


# ── VeilClipWindow ────────────────────────────────────────────────────────────

class VeilClipWindow(QWidget):

    CURSOR_PAD_X  = 12
    SCREEN_H_PCT  = 0.80

    def __init__(self, db=None, on_open_settings=None, on_open_donate=None, on_open_help=None, parent=None) -> None:
        super().__init__(parent)
        self._db                = db
        self._on_open_settings  = on_open_settings
        self._on_open_donate    = on_open_donate
        self._on_open_help      = on_open_help
        self._acrylic_applied   = False
        self._cards: list[ClipboardItemCard] = []
        self._card_cache: dict[int, ClipboardItemCard] = {}   # id → card reuse cache
        self._all_items: list[dict] = []
        self._group_mode        = False
        self._close_after_copy        = True   # configurable via settings
        self._close_on_outside_click  = False  # configurable via settings

        # Position memory (#5)
        self._opened_before   = False
        self._open_at_cursor  = False
        self._last_pos: QPoint | None = None

        try:
            icon_path = Path(ICON_APP)
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            pass

        # Drag state
        self._drag_active    = False
        self._drag_start_pos = QPoint()

        # Per-instance sibling window list (instance-level, not class-level)
        self._sibling_windows: list = []

        # Dirty flag for batched UI refresh (avoids double _apply_filter calls)
        self._needs_refresh: bool = False

        # Global mouse filter for close-on-outside-click
        self._outside_filter = _OutsideClickFilter(self)

        # Multi-select state (initialised here; also reset in _build_ui)
        self._select_mode    = False
        self._selected_ids: set[int] = set()

        self._setup_window()
        self._build_ui()
        self._restore_geometry()

        # Safety-net live refresh: polls DB every 500 ms while the panel is
        # open. Catches any update that slipped past notify_new_item (e.g. edits,
        # external DB writes, or race-condition gaps).
        self._live_refresh_timer = QTimer(self)
        self._live_refresh_timer.setInterval(500)
        self._live_refresh_timer.timeout.connect(self._live_refresh_tick)

    # ── Window setup ──────────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(MIN_W, MIN_H)
        self.resize(DEFAULT_W, DEFAULT_H)
        self.setWindowOpacity(0.97)
        QApplication.instance().installEventFilter(self)

    def _restore_geometry(self) -> None:
        """Load saved size and settings from config.json if available."""
        try:
            w = _cfg.get("window_w", DEFAULT_W)
            h = _cfg.get("window_h", DEFAULT_H)
            self._open_at_cursor         = _cfg.get("open_at_cursor", False)
            self._close_after_copy       = _cfg.get("close_after_copy", True)
            self._close_on_outside_click = _cfg.get("close_on_outside_click", False)
            if _cfg.get("always_on_top", True):
                self._apply_always_on_top_flag(True)
            self.resize(
                max(MIN_W, min(w, 1200)),
                max(MIN_H, min(h, 1000)),
            )
        except Exception:
            pass

    def _save_geometry(self) -> None:
        try:
            _cfg.update({"window_w": self.width(), "window_h": self.height()})
        except Exception:
            pass

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._container = QWidget()
        self._container.setObjectName("container")
        self._container.setStyleSheet("""
            QWidget#container {
                background: rgba(15,17,23,0.93);
                border: 1px solid rgba(108,99,255,0.25);
                border-radius: 14px;
            }
        """)

        inner = QVBoxLayout(self._container)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)

        inner.addWidget(self._make_header())
        inner.addWidget(self._make_search_bar())
        inner.addWidget(self._make_multiselect_toolbar())
        inner.addWidget(self._make_welcome_banner())
        inner.addWidget(self._make_list_area(), stretch=1)
        inner.addWidget(self._make_favorites_panel(), stretch=1)
        inner.addWidget(self._make_resize_grip())

        self._search.textChanged.connect(self._on_search_changed)

        # Show clipboard tab by default
        self._favorites_panel.setVisible(False)
        self._active_tab = "pano"

        root.addWidget(self._container)

        # Toast overlay (#4)
        self._toast = _Toast(self)

        # Undo stack — list of (undo_cb, commit_cb, timer) for up to 8 pending deletes
        # Each entry: {"items": [...], "positions": [...], "commit_cb": fn, "timer": QTimer}
        self._undo_stack: list[dict] = []
        # Set of item IDs that are pending deletion (removed from UI, not yet from DB)
        self._pending_deletions: set = set()

        # Legacy single-item undo (kept for Ctrl+Z compatibility)
        self._pending_undo_item = None
        self._pending_undo_pos  = None
        self._pending_undo_cb   = None

        # Multi-select state
        self._select_mode = False
        self._selected_ids: set[int] = set()

    # ── Header ────────────────────────────────────────────────────────────────

    # ── Header (tabs + controls in one row) ──────────────────────────────────

    def _make_header(self) -> QWidget:
        self._header = QWidget()
        self._header.setFixedHeight(52)
        self._header.setStyleSheet("""
            background: rgba(26,29,39,0.95);
            border-radius: 14px 14px 0 0;
        """)
        self._header.setCursor(Qt.CursorShape.SizeAllCursor)

        h = QHBoxLayout(self._header)
        h.setContentsMargins(14, 0, 10, 0)
        h.setSpacing(6)

        # App icon
        icon_path = Path(ICON_APP)
        if icon_path.exists():
            il = QLabel()
            il.setPixmap(QIcon(str(icon_path)).pixmap(18, 18))
            il.setStyleSheet("background:transparent;")
            h.addWidget(il)

        # App title
        title = QLabel(i18n.get("main.title"))
        title.setStyleSheet(f"color:{TEXT}; font-family:'Segoe UI',sans-serif; "
                            f"font-size:13px; font-weight:700; background:transparent; border:none;")
        h.addWidget(title)

        # Thin vertical separator
        sep = QWidget()
        sep.setFixedSize(1, 20)
        sep.setStyleSheet(f"background:{BORDER}; border:none;")
        h.addWidget(sep)

        # Tab buttons — Clipboard / Favorites
        self._tab_pano = QPushButton("Clipboard")
        self._tab_pano.setFixedHeight(28)
        self._tab_pano.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tab_pano.clicked.connect(lambda: self._switch_tab("pano"))

        self._tab_fav = QPushButton("Favorites")
        self._tab_fav.setFixedHeight(28)
        self._tab_fav.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tab_fav.clicked.connect(lambda: self._switch_tab("favorites"))

        h.addWidget(self._tab_pano)
        h.addWidget(self._tab_fav)
        self._refresh_tab_style("pano")

        h.addStretch()

        # Item count
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-family:'Segoe UI',sans-serif; "
                                      f"font-size:11px; background:transparent; border:none;")
        h.addWidget(self._count_lbl)

        # Select button — shown only on Clipboard tab
        self._select_btn = QPushButton("Select")
        self._select_btn.setFixedHeight(26)
        self._select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._select_btn.setToolTip("Select multiple items to copy or delete")
        self._select_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{TEXT_DIM}; border:1px solid {BORDER};
                          border-radius:6px; font-family:'Segoe UI',sans-serif;
                          font-size:10px; font-weight:600; padding:0 8px; }}
            QPushButton:hover {{ background:{BG_HOVER}; color:{TEXT}; border-color:{ACCENT_DIM}; }}
        """)
        self._select_btn.clicked.connect(self._enter_select_mode)
        h.addWidget(self._select_btn)

        # Help (ℹ)
        help_btn = QPushButton("ℹ")
        help_btn.setFixedSize(26, 26)
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.setToolTip("Help & Support")
        help_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{TEXT_DIM}; border:none;
                          border-radius:6px; font-size:14px; font-weight:700; }}
            QPushButton:hover   {{ background:{BG_HOVER}; color:#7FC8FF; }}
            QPushButton:pressed {{ background:{ACCENT}; color:white; }}
        """)
        help_btn.clicked.connect(self._open_help)
        h.addWidget(help_btn)

        # Donate (💜)
        donate_btn = QPushButton("💜")
        donate_btn.setFixedSize(26, 26)
        donate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        donate_btn.setToolTip("Support the Developer")
        donate_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{TEXT_DIM}; border:none;
                          border-radius:6px; font-size:14px; }}
            QPushButton:hover   {{ background:{BG_HOVER}; color:#CC99FF; }}
            QPushButton:pressed {{ background:{ACCENT}; color:white; }}
        """)
        donate_btn.clicked.connect(self._open_donate)
        h.addWidget(donate_btn)

        # Settings (⚙)
        settings_btn = QPushButton("⚙")
        settings_btn.setFixedSize(26, 26)
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setToolTip("Settings")
        settings_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{TEXT_DIM}; border:none;
                          border-radius:6px; font-size:14px; }}
            QPushButton:hover   {{ background:{BG_HOVER}; color:{TEXT}; }}
            QPushButton:pressed {{ background:{ACCENT}; color:white; }}
        """)
        settings_btn.clicked.connect(self._open_settings)
        h.addWidget(settings_btn)

        # Close (✕)
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{TEXT_DIM}; border:none;
                          border-radius:6px; font-size:12px; font-weight:700; }}
            QPushButton:hover   {{ background:{RED_DIM}; color:{RED}; }}
            QPushButton:pressed {{ background:{RED}; color:white; }}
        """)
        close_btn.clicked.connect(self.hide_window)
        h.addWidget(close_btn)

        return self._header

    def _refresh_tab_style(self, active: str) -> None:
        active_style = f"""
            QPushButton {{ background:{ACCENT}; color:white; border:none;
                          border-radius:6px; font-family:'Segoe UI',sans-serif;
                          font-size:11px; font-weight:700; padding:0 12px; }}
            QPushButton:hover {{ background:#7D75FF; }}
        """
        inactive_style = f"""
            QPushButton {{ background:transparent; color:{TEXT_DIM}; border:none;
                          border-radius:6px; font-family:'Segoe UI',sans-serif;
                          font-size:11px; font-weight:600; padding:0 12px; }}
            QPushButton:hover {{ background:{BG_HOVER}; color:{TEXT}; }}
        """
        self._tab_pano.setStyleSheet(active_style if active == "pano" else inactive_style)
        self._tab_fav.setStyleSheet(active_style if active == "favorites" else inactive_style)

    def _switch_tab(self, tab: str) -> None:
        self._active_tab = tab
        self._refresh_tab_style(tab)
        is_pano = tab == "pano"
        self._scroll.setVisible(is_pano)
        self._search_wrapper.setVisible(is_pano)
        self._fav_search_wrapper.setVisible(not is_pano)
        self._select_btn.setVisible(is_pano)      # hide Select on Favorites tab
        self._multiselect_toolbar.setVisible(False)
        self._favorites_panel.setVisible(not is_pano)
        if not is_pano:
            if self._select_mode:
                self._exit_select_mode()
            self._refresh_favorites_panel()
        else:
            # Back to clipboard — restore clipboard count
            n = len(self._all_items)
            self._count_lbl.setText(i18n.get("main.count_items", count=n) if n else "")

    # ── Multi-select toolbar ──────────────────────────────────────────────────

    def _make_multiselect_toolbar(self) -> QWidget:
        self._multiselect_toolbar = QWidget()
        self._multiselect_toolbar.setFixedHeight(40)
        self._multiselect_toolbar.setStyleSheet(
            f"background:rgba(108,99,255,0.12); border-bottom:1px solid {ACCENT_DIM};"
        )
        self._multiselect_toolbar.setVisible(False)

        h = QHBoxLayout(self._multiselect_toolbar)
        h.setContentsMargins(10, 0, 10, 0)
        h.setSpacing(6)

        self._sel_count_lbl = QLabel(i18n.get("main.selected_count", count=0))
        self._sel_count_lbl.setStyleSheet(
            f"color:{TEXT_DIM}; font-family:'Segoe UI',sans-serif; font-size:11px; background:transparent;"
        )
        h.addWidget(self._sel_count_lbl)
        h.addStretch()

        copy_btn = QPushButton("Copy")
        copy_btn.setFixedHeight(26)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet(btn_primary())
        copy_btn.clicked.connect(self._multiselect_copy)
        h.addWidget(copy_btn)

        del_btn = QPushButton("Delete")
        del_btn.setFixedHeight(26)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(btn_danger())
        del_btn.clicked.connect(self._multiselect_delete)
        h.addWidget(del_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(26)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(btn_ghost())
        cancel_btn.clicked.connect(self._exit_select_mode)
        h.addWidget(cancel_btn)

        return self._multiselect_toolbar

    # ── Favorites panel ───────────────────────────────────────────────────────

    def _make_favorites_panel(self) -> QWidget:
        self._favorites_panel = QWidget()
        self._favorites_panel.setStyleSheet("background:transparent;")

        v = QVBoxLayout(self._favorites_panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self._fav_search_wrapper = self._make_favorites_search_bar()
        self._fav_search_wrapper.setVisible(False)
        v.addWidget(self._fav_search_wrapper)

        # Category bar
        self._fav_cat_bar = QWidget()
        self._fav_cat_bar.setFixedHeight(40)
        self._fav_cat_bar.setStyleSheet(f"background:rgba(26,29,39,0.6); border:none;")
        cat_h = QHBoxLayout(self._fav_cat_bar)
        cat_h.setContentsMargins(8, 4, 8, 4)
        cat_h.setSpacing(4)
        self._fav_cat_layout = cat_h
        v.addWidget(self._fav_cat_bar)

        # Favorites scroll list
        self._fav_scroll = QScrollArea()
        self._fav_scroll.setWidgetResizable(True)
        self._fav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._fav_scroll.setStyleSheet(scrollbar_style())

        self._fav_list_widget = QWidget()
        self._fav_list_widget.setStyleSheet("background:transparent;")
        self._fav_list_layout = QVBoxLayout(self._fav_list_widget)
        self._fav_list_layout.setContentsMargins(8, 8, 8, 8)
        self._fav_list_layout.setSpacing(4)

        # Rich empty state — shown when there are no favorites
        self._fav_empty_widget = QWidget()
        self._fav_empty_widget.setStyleSheet("background:transparent;")
        _ev = QVBoxLayout(self._fav_empty_widget)
        _ev.setContentsMargins(20, 40, 20, 40)
        _ev.setSpacing(8)
        _ev.setAlignment(Qt.AlignmentFlag.AlignCenter)

        _star = QLabel("★")
        _star.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _star.setStyleSheet(
            f"color:{TEXT_DIM}; font-size:32px; background:transparent; border:none;"
        )
        _ev.addWidget(_star)

        _fav_title = QLabel(i18n.get("main.no_favorites_title"))
        _fav_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _fav_title.setStyleSheet(
            f"color:{TEXT_DIM}; font-family:'Segoe UI',sans-serif; "
            f"font-size:13px; font-weight:600; background:transparent; border:none;"
        )
        _ev.addWidget(_fav_title)

        _fav_hint = QLabel(i18n.get("main.no_favorites_hint"))
        _fav_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _fav_hint.setWordWrap(True)
        _fav_hint.setStyleSheet(
            f"color:{TEXT_DIM}; font-family:'Segoe UI',sans-serif; "
            f"font-size:11px; background:transparent; border:none;"
        )
        _ev.addWidget(_fav_hint)

        self._fav_list_layout.addWidget(self._fav_empty_widget)
        self._fav_list_layout.addStretch()

        self._fav_scroll.setWidget(self._fav_list_widget)
        v.addWidget(self._fav_scroll, stretch=1)

        self._fav_active_category: str | None = None  # None = show all
        return self._favorites_panel

    # ── Welcome banner (first run only) ──────────────────────────────────────

    def _make_welcome_banner(self) -> QWidget:
        """Build the first-run welcome banner (hidden by default)."""
        self._welcome_banner = QWidget()
        self._welcome_banner.setVisible(False)
        self._welcome_banner.setStyleSheet(
            f"background:rgba(108,99,255,0.12);"
            f"border-bottom:1px solid {ACCENT_DIM};"
        )

        h = QHBoxLayout(self._welcome_banner)
        h.setContentsMargins(14, 8, 10, 8)
        h.setSpacing(10)

        msg = QLabel(i18n.get("main.welcome_message"))
        msg.setWordWrap(True)
        msg.setStyleSheet(
            f"color:{TEXT}; font-family:'Segoe UI',sans-serif;"
            f"font-size:11px; background:transparent; border:none;"
        )
        h.addWidget(msg, stretch=1)

        got_it = QPushButton("Got it")
        got_it.setFixedHeight(26)
        got_it.setCursor(Qt.CursorShape.PointingHandCursor)
        got_it.setStyleSheet(
            f"QPushButton {{ background:{ACCENT}; color:white; border:none;"
            f" border-radius:6px; font-family:'Segoe UI',sans-serif;"
            f" font-size:11px; font-weight:700; padding:0 12px; }}"
            f"QPushButton:hover {{ background:#7D75FF; }}"
        )
        got_it.clicked.connect(self._dismiss_welcome_banner)
        h.addWidget(got_it)

        return self._welcome_banner

    def _show_welcome_hint(self) -> None:
        """Show the welcome banner if this is the first run."""
        try:
            if _cfg.get("first_run", False):
                self._welcome_banner.setVisible(True)
        except Exception:
            pass

    def _dismiss_welcome_banner(self) -> None:
        """Hide the banner and mark first_run as done in config."""
        self._welcome_banner.setVisible(False)
        try:
            _cfg.set("first_run", False)
        except Exception:
            pass

    # ── Search bar ────────────────────────────────────────────────────────────

    def _make_search_bar(self) -> QWidget:
        self._search_wrapper = QWidget()
        self._search_wrapper.setFixedHeight(48)
        self._search_wrapper.setStyleSheet(f"background:rgba(26,29,39,0.6); border:none;")

        h = QHBoxLayout(self._search_wrapper)
        h.setContentsMargins(10, 8, 10, 8)
        h.setSpacing(6)

        h.addWidget(QLabel("🔍", styleSheet="font-size:13px; background:transparent;"))

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search clipboard history…")
        self._search.setStyleSheet(f"""
            QLineEdit {{ background:transparent; border:none; color:{TEXT};
                        font-family:'Segoe UI',sans-serif; font-size:12px; }}
        """)
        h.addWidget(self._search, stretch=1)

        self._clear_search_btn = QPushButton("✕")
        self._clear_search_btn.setFixedSize(18, 18)
        self._clear_search_btn.setVisible(False)
        self._clear_search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_search_btn.setStyleSheet(f"""
            QPushButton {{ background:{BG_HOVER}; color:{TEXT_DIM}; border:none;
                          border-radius:9px; font-size:9px; font-weight:700; }}
            QPushButton:hover {{ color:{TEXT}; }}
        """)
        self._clear_search_btn.clicked.connect(self._clear_search)
        h.addWidget(self._clear_search_btn)

        # Group toggle
        self._group_btn = QPushButton("⊞  Group")
        self._group_btn.setFixedHeight(26)
        self._group_btn.setCheckable(True)
        self._group_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._group_btn.setToolTip("Group by source application")
        self._group_btn.clicked.connect(self._on_group_clicked)
        self._refresh_group_btn_style(False)
        h.addWidget(self._group_btn)

        return self._search_wrapper

    def _make_favorites_search_bar(self) -> QWidget:
        self._fav_search_wrapper = QWidget()
        self._fav_search_wrapper.setFixedHeight(48)
        self._fav_search_wrapper.setStyleSheet(f"background:rgba(26,29,39,0.6); border:none;")

        h = QHBoxLayout(self._fav_search_wrapper)
        h.setContentsMargins(10, 8, 10, 8)
        h.setSpacing(6)

        h.addWidget(QLabel("🔍", styleSheet="font-size:13px; background:transparent;"))

        self._fav_search = QLineEdit()
        self._fav_search.setPlaceholderText(i18n.get("favorites.search_placeholder"))
        self._fav_search.setStyleSheet(f"""
            QLineEdit {{ background:transparent; border:none; color:{TEXT};
                        font-family:'Segoe UI',sans-serif; font-size:12px; }}
        """)
        h.addWidget(self._fav_search, stretch=1)

        self._fav_clear_search_btn = QPushButton("✕")
        self._fav_clear_search_btn.setFixedSize(18, 18)
        self._fav_clear_search_btn.setVisible(False)
        self._fav_clear_search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fav_clear_search_btn.setStyleSheet(f"""
            QPushButton {{ background:{BG_HOVER}; color:{TEXT_DIM}; border:none;
                          border-radius:9px; font-size:9px; font-weight:700; }}
            QPushButton:hover {{ color:{TEXT}; }}
        """)
        self._fav_clear_search_btn.clicked.connect(self._clear_fav_search)
        h.addWidget(self._fav_clear_search_btn)

        self._fav_search.textChanged.connect(self._on_fav_search_changed)
        return self._fav_search_wrapper

    # ── List area ─────────────────────────────────────────────────────────────

    def _make_list_area(self) -> QWidget:
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(scrollbar_style())

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet("background:transparent;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(8, 8, 8, 8)
        self._list_layout.setSpacing(4)

        self._empty_lbl = QLabel(i18n.get("main.empty_default"))
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-family:'Segoe UI',sans-serif; "
                                      f"font-size:12px; padding:40px 20px; background:transparent;")
        self._list_layout.addWidget(self._empty_lbl)
        self._list_layout.addStretch()

        self._scroll.setWidget(self._list_widget)
        return self._scroll

    # ── Resize grip ───────────────────────────────────────────────────────────

    def _make_resize_grip(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(18)
        bar.setStyleSheet(f"background:rgba(26,29,39,0.6); border-radius:0 0 14px 14px;")
        h = QHBoxLayout(bar)
        h.setContentsMargins(0, 0, 4, 2)
        h.addStretch()
        grip = QSizeGrip(self)
        grip.setStyleSheet("background:transparent;")
        h.addWidget(grip)
        return bar

    # ── Public API ────────────────────────────────────────────────────────────

    def toggle(self) -> None:
        if self.isVisible():
            self.hide_window()
        else:
            self.show_window()

    def show_window(self) -> None:
        # Cancel any pending auto-close from a previous toast
        if hasattr(self, "_toast"):
            self._toast._after_timer.stop()
            self._toast._after_cb = None

        self.refresh_items()
        self.move(self._calculate_position())
        self.show()
        self.raise_()
        self.activateWindow()
        self._live_refresh_timer.start()
        self._opened_before = True

        # Show first-run welcome banner if applicable
        self._show_welcome_hint()

        # Install global mouse filter for close-on-outside-click
        self._outside_filter.install()

        if not self._acrylic_applied:
            self._acrylic_applied = _apply_acrylic(int(self.winId()))

        logger.debug("Window shown at %s  size=%sx%s", self.pos(), self.width(), self.height())

    # Keep old name as alias
    def show_at_cursor(self) -> None:
        self.show_window()

    def hide_window(self) -> None:
        self._last_pos = self.pos()
        self._save_geometry()
        self._live_refresh_timer.stop()
        self._outside_filter.uninstall()
        self.hide()
        self._clear_search()
        # Commit all pending deletes immediately — undo is no longer possible
        self._flush_undo_stack()
        logger.debug("Window hidden.")

    def _invalidate(self) -> None:
        """Mark the UI as needing a refresh on the next timer tick."""
        self._needs_refresh = True

    def _live_refresh_tick(self) -> None:
        """Periodic DB poll while the panel is open.

        Uses a cheap query instead of fetching all rows every 500 ms.
        Only pulls the full item list when a change is detected.
        If _needs_refresh is True (set by notify_new_item), the filter
        is applied immediately without a DB poll.
        """
        if self._db is None or not self.isVisible():
            return

        # If a new item was just added via notify_new_item, apply immediately
        if self._needs_refresh:
            self._needs_refresh = False
            self._apply_filter(self._search.text())
            return

        try:
            new_hash = self._db.get_change_hash()
        except Exception:
            return
        old_hash = getattr(self, "_last_change_hash", None)
        if new_hash == old_hash:
            return   # nothing changed — skip full reload
        self._last_change_hash = new_hash
        try:
            latest = self._db.get_all_items()
        except Exception:
            return
        # Filter out any items that are pending deletion (removed from UI, not yet committed to DB)
        if self._pending_deletions:
            latest = [i for i in latest if i["id"] not in self._pending_deletions]
        self._all_items        = latest
        self._last_refresh_sig = [(i["id"], i.get("content_text") or "") for i in latest]
        self._apply_filter(self._search.text())

    def notify_new_item(self, item: dict) -> None:
        """Called (on Qt main thread via QTimer.singleShot) when a new clipboard
        item is saved.  Updates _all_items and sets the dirty flag so the next
        timer tick will rebuild the list — avoiding double _apply_filter calls.
        """
        if self._db is None:
            return
        try:
            fresh = self._db.get_all_items()
            # Filter out items pending deletion
            if self._pending_deletions:
                fresh = [i for i in fresh if i["id"] not in self._pending_deletions]
            self._all_items = fresh
        except Exception as exc:
            logger.error("Failed to refresh items: %s", exc)
            return

        self._invalidate()
        if self.isVisible():
            QTimer.singleShot(30, self._scroll_to_top)

    def _scroll_to_top(self) -> None:
        sb = self._scroll.verticalScrollBar()
        if sb:
            sb.setValue(0)

    def show_copy_toast(self, msg: str | None = None) -> None:
        """Display the copy confirmation toast, then close if configured."""
        after = self.hide_window if self._close_after_copy else None
        self._toast.show_message(msg or i18n.get("notifications.copied"), duration_ms=600, after=after)

    def _open_settings(self) -> None:
        """Open settings window — delegates to main.py callback if set."""
        if self._on_open_settings:
            self._on_open_settings()

    def _open_donate(self) -> None:
        """Open donate window — delegates to main.py callback if set."""
        if self._on_open_donate:
            self._on_open_donate()

    def _open_help(self) -> None:
        """Open help window — delegates to main.py callback if set."""
        if self._on_open_help:
            self._on_open_help()

    # ── Geometry ──────────────────────────────────────────────────────────────

    def _calculate_position(self) -> QPoint:
        screen = QApplication.primaryScreen().availableGeometry()
        w, h   = self.width(), self.height()

        use_cursor = (
            not self._opened_before          # always use cursor on very first open
            or self._open_at_cursor          # user chose "always at cursor" in settings
        )

        if use_cursor:
            cx, cy = get_cursor_position()
            x = cx + self.CURSOR_PAD_X
            y = cy
            if x + w > screen.right():
                x = cx - w - self.CURSOR_PAD_X
            if y + h > screen.bottom():
                y = screen.bottom() - h
            return QPoint(
                max(screen.left(), x),
                max(screen.top(),  y),
            )

        # Subsequent opens → last known position (clamped to screen)
        if self._last_pos is not None:
            p = self._last_pos
            x = max(screen.left(), min(p.x(), screen.right()  - w))
            y = max(screen.top(),  min(p.y(), screen.bottom() - h))
            return QPoint(x, y)

        # Fallback to cursor
        cx, cy = get_cursor_position()
        x = cx + self.CURSOR_PAD_X
        y = cy
        if x + w > screen.right():
            x = cx - w - self.CURSOR_PAD_X
        if y + h > screen.bottom():
            y = screen.bottom() - h
        return QPoint(max(screen.left(), x), max(screen.top(), y))

    def set_open_at_cursor(self, value: bool) -> None:
        """Called from settings window.

        value=True  → always open at mouse cursor position.
        value=False → first open at cursor, then reopen at last closed position.
        """
        self._open_at_cursor = value
        try:
            _cfg.set("open_at_cursor", value)
        except Exception:
            pass
        logger.debug("open_at_cursor set to %s", value)

    def set_close_after_copy(self, value: bool) -> None:
        """Called from settings window — controls whether the panel closes after copying."""
        self._close_after_copy = value
        try:
            _cfg.set("close_after_copy", value)
        except Exception:
            pass
        logger.debug("close_after_copy set to %s", value)

    def set_always_on_top(self, value: bool) -> None:
        """Apply or remove WindowStaysOnTopHint on the clipboard panel."""
        self._apply_always_on_top_flag(value)
        logger.debug("always_on_top set to %s", value)

    def _apply_always_on_top_flag(self, enabled: bool) -> None:
        visible = self.isVisible()
        flags = (
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        if enabled:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        if visible:
            self.show()

    def set_close_on_outside_click(self, value: bool) -> None:
        """Toggle whether clicking outside the panel dismisses it."""
        self._close_on_outside_click = value
        try:
            _cfg.set("close_on_outside_click", value)
        except Exception:
            pass
        logger.debug("close_on_outside_click set to %s", value)

    # ── Item list management ──────────────────────────────────────────────────

    def refresh_items(self) -> None:
        if self._db is None:
            return
        try:
            self._all_items = self._db.get_all_items()
        except Exception as exc:
            logger.error("Failed to load items: %s", exc)
            return
        self._apply_filter(self._search.text())

    def _apply_filter(self, query: str) -> None:
        q = query.strip()
        visible = [i for i in self._all_items if _matches(i, q)] if q else list(self._all_items)
        if self._group_mode:
            self._rebuild_grouped(visible, query=q)
        else:
            self._rebuild_flat(visible, query=q)

    def _rebuild_flat(self, items: list[dict], query: str = "") -> None:
        """Rebuild the flat list view using a diff to avoid full destroy/recreate.

        Cards whose item content has not changed are reused from _card_cache.
        Only new or changed cards are constructed.  Deleted items have their
        cards removed from the cache and the layout.
        """
        if not items:
            self._clear_list()
            self._show_empty(query)
            self.update()
            return

        self._empty_lbl.setVisible(False)
        self._count_lbl.setText(i18n.get("main.count_items", count=len(items)))

        # Build a signature for each incoming item (id + pinned + text snippet)
        def _item_sig(it: dict) -> tuple:
            return (
                it["id"],
                it.get("is_pinned", 0),
                (it.get("content_text") or "")[:80],
            )

        new_ids     = [i["id"] for i in items]
        new_id_set  = set(new_ids)
        new_sig_map = {i["id"]: _item_sig(i) for i in items}

        # Remove cards that are no longer in the list
        stale_ids = [iid for iid in list(self._card_cache) if iid not in new_id_set]
        for iid in stale_ids:
            card = self._card_cache.pop(iid)
            self._list_layout.removeWidget(card)
            card.setParent(None)

        # Build final ordered card list — reuse or create
        self._cards.clear()
        for item in items:
            iid = item["id"]
            sig = new_sig_map[iid]
            old_card = self._card_cache.get(iid)

            if old_card is not None and getattr(old_card, "_cache_sig", None) == sig:
                # Reuse existing card — just ensure select mode is consistent
                if self._select_mode:
                    old_card.set_select_mode(True)
                self._cards.append(old_card)
            else:
                # Create new card (item is new or content changed)
                if old_card is not None:
                    self._list_layout.removeWidget(old_card)
                    old_card.setParent(None)
                new_card = self._make_card(item)
                new_card._cache_sig = sig
                self._card_cache[iid] = new_card
                self._cards.append(new_card)

        # Re-order layout to match the desired display order
        # Remove empty_lbl and stretch, insert cards in order, re-add them
        for idx in range(self._list_layout.count() - 1, -1, -1):
            layout_item = self._list_layout.itemAt(idx)
            if layout_item is None:
                continue
            w = layout_item.widget()
            if w is not None and w is not self._empty_lbl:
                self._list_layout.removeWidget(w)

        for card in self._cards:
            self._list_layout.insertWidget(self._list_layout.count() - 1, card)

        self.update()

    def _rebuild_grouped(self, items: list[dict], query: str = "") -> None:
        """Group mode always does a full rebuild (headers break simple diffing)."""
        self._clear_list()
        if not items:
            self._show_empty(query); self.update(); return
        self._empty_lbl.setVisible(False)
        self._count_lbl.setText(i18n.get("main.count_items", count=len(items)))

        pinned   = [i for i in items if i.get("is_pinned")]
        unpinned = [i for i in items if not i.get("is_pinned")]

        if pinned:
            self._insert_widget(_GroupHeader(i18n.get("main.group_pinned"), len(pinned)))
            for item in pinned:
                card = self._make_card(item); self._insert_widget(card); self._cards.append(card)

        groups: dict[str, list] = defaultdict(list)
        for item in unpinned:
            groups[(item.get("source_app") or i18n.get("common.unknown")).strip() or i18n.get("common.unknown")].append(item)

        for src, grp in groups.items():
            self._insert_widget(_GroupHeader(src, len(grp)))
            for item in grp:
                card = self._make_card(item); self._insert_widget(card); self._cards.append(card)

        self.update()

    def _clear_list(self) -> None:
        """Full clear — destroys all cards and resets the cache."""
        self._cards.clear()
        self._card_cache.clear()
        to_remove = []
        for idx in range(self._list_layout.count()):
            layout_item = self._list_layout.itemAt(idx)
            if layout_item is None:
                continue
            w = layout_item.widget()
            if w is not None and w is not self._empty_lbl:
                to_remove.append(w)
        for w in to_remove:
            self._list_layout.removeWidget(w)
            w.setParent(None)

    def _insert_widget(self, widget: QWidget) -> None:
        self._list_layout.insertWidget(self._list_layout.count() - 1, widget)

    def _make_card(self, item: dict) -> ClipboardItemCard:
        card = ClipboardItemCard(
            item=item,
            on_close=self.hide_window,
            on_copy=self.show_copy_toast,
            on_item_edited=self._on_item_edited,
            close_after_copy=self._close_after_copy,
            db=self._db,
        )
        card.pin_toggled.connect(self._on_pin_toggled)
        card.delete_requested.connect(self._on_delete_requested)
        card.selection_changed.connect(self._on_card_selection_changed)
        # Apply current select mode immediately
        if self._select_mode:
            card.set_select_mode(True)
        return card

    def _apply_filter_from_current_search(self) -> None:
        """Helper: apply filter using the current search text."""
        self._apply_filter(self._search.text())

    def _on_item_edited(self) -> None:
        """Called after an in-card text edit — update cache and rebuild list."""
        if self._db is None:
            return
        try:
            fresh = self._db.get_all_items()
        except Exception as exc:
            logger.error("Edit refresh failed: %s", exc)
            return
        # Patch _all_items in-place so the live-refresh tick doesn't fight us
        self._all_items = fresh
        # Defer the rebuild to the next event loop cycle to avoid re-entrancy risk
        QTimer.singleShot(0, self._apply_filter_from_current_search)
        # Update the live-refresh signature so the next tick doesn't re-trigger
        self._last_refresh_sig = [
            (i["id"], i.get("content_text") or "") for i in fresh
        ]

    def _show_empty(self, query: str) -> None:
        self._empty_lbl.setText(
            i18n.get("main.no_results", query=query) if query else i18n.get("main.empty_default")
        )
        self._empty_lbl.setVisible(True)
        self._count_lbl.setText("")

    # ── Group toggle ──────────────────────────────────────────────────────────

    def _on_group_clicked(self) -> None:
        # Use clicked signal (not toggled) to avoid double-fire bug
        active = self._group_btn.isChecked()
        if active == self._group_mode:
            return   # state unchanged — do nothing
        self._group_mode = active
        self._refresh_group_btn_style(active)
        self._apply_filter(self._search.text())

    def _refresh_group_btn_style(self, active: bool) -> None:
        if active:
            self._group_btn.setStyleSheet(f"""
                QPushButton {{ background:{ACCENT}; color:white; border:none; border-radius:6px;
                              font-family:'Segoe UI',sans-serif; font-size:10px; font-weight:700; padding:0 8px; }}
                QPushButton:hover {{ background:#7D75FF; }}
            """)
        else:
            self._group_btn.setStyleSheet(f"""
                QPushButton {{ background:transparent; color:{TEXT_DIM}; border:1px solid {BORDER}; border-radius:6px;
                              font-family:'Segoe UI',sans-serif; font-size:10px; font-weight:600; padding:0 8px; }}
                QPushButton:hover {{ background:{BG_HOVER}; color:{TEXT}; border-color:{ACCENT_DIM}; }}
            """)

    # ── Search ────────────────────────────────────────────────────────────────

    def _on_search_changed(self, text: str) -> None:
        self._clear_search_btn.setVisible(bool(text.strip()))
        self._apply_filter(text)

    def _clear_search(self) -> None:
        self._search.clear()
        self._clear_search_btn.setVisible(False)

    def _on_fav_search_changed(self, text: str) -> None:
        self._fav_clear_search_btn.setVisible(bool(text.strip()))
        self._rebuild_favorites_list()

    def _clear_fav_search(self) -> None:
        self._fav_search.clear()
        self._fav_clear_search_btn.setVisible(False)
        self._rebuild_favorites_list()

    # ── Card signal handlers ──────────────────────────────────────────────────

    def _on_pin_toggled(self, item_id: int) -> None:
        if self._db:
            # Save current scroll position before toggling
            sb = self._scroll.verticalScrollBar()
            scroll_pos = sb.value() if sb else 0
            self._db.toggle_pin(item_id)
            self.refresh_items()
            # Restore scroll position after rebuild
            if sb:
                QTimer.singleShot(10, lambda: sb.setValue(scroll_pos))

    def _on_delete_requested(self, item_id: int) -> None:
        """Handle single-item delete with a 3-second undo window.

        The item is deleted from the DB immediately so it never comes back.
        If the user clicks Undo within 3 seconds, the item is re-inserted.
        """
        MAX_UNDO = 8
        UNDO_MS  = 3_000

        deleted_item = next((i for i in self._all_items if i["id"] == item_id), None)
        deleted_pos  = next((idx for idx, i in enumerate(self._all_items) if i["id"] == item_id), None)
        if deleted_item is None:
            return

        # 1. Delete from DB right away — no more "comes back on refresh" bug
        if self._db:
            self._db.delete_item(item_id)

        # 2. Remove from in-memory list and UI
        self._all_items = [i for i in self._all_items if i["id"] != item_id]
        self._pending_deletions.add(item_id)   # still block live-refresh from re-adding
        card = self._card_cache.pop(item_id, None)
        if card:
            self._list_layout.removeWidget(card)
            card.setParent(None)
        self._apply_filter(self._search.text())

        def _on_undo_expired() -> None:
            """Undo window closed — remove from pending set, update toast."""
            self._pending_deletions.discard(item_id)
            self._undo_stack = [e for e in self._undo_stack if e.get("item_id") != item_id]
            self._update_undo_toast()

        def _undo() -> None:
            """Re-insert the item by writing it back to the DB."""
            self._pending_deletions.discard(item_id)
            self._undo_stack = [e for e in self._undo_stack if e.get("item_id") != item_id]
            # Re-add to DB
            if self._db and deleted_item is not None:
                try:
                    self._db.restore_item(deleted_item)
                except Exception:
                    # Fallback: add_item with original data
                    try:
                        self._db.add_item(
                            deleted_item.get("content_type", "text"),
                            deleted_item.get("size_bytes", 0),
                            content_text=deleted_item.get("content_text"),
                            content_blob=deleted_item.get("content_blob"),
                            source_app=deleted_item.get("source_app"),
                        )
                    except Exception as exc:
                        logger.error("Undo re-insert failed: %s", exc)
            # Restore in-memory
            if deleted_pos is not None:
                self._all_items.insert(min(deleted_pos, len(self._all_items)), deleted_item)
            else:
                self._all_items.append(deleted_item)
            self._apply_filter(self._search.text())
            self._update_undo_toast()

        # Expiry timer — after 3 s just clean up the UI state (DB already deleted)
        expire_timer = QTimer(self)
        expire_timer.setSingleShot(True)
        expire_timer.timeout.connect(_on_undo_expired)
        expire_timer.start(UNDO_MS)

        entry = {
            "item_id":   item_id,
            "undo_cb":   _undo,
            "commit_cb": _on_undo_expired,   # alias used by _flush_undo_stack
            "timer":     expire_timer,
        }

        # Trim stack
        if len(self._undo_stack) >= MAX_UNDO:
            oldest = self._undo_stack.pop(0)
            oldest["timer"].stop()
            oldest["commit_cb"]()

        self._undo_stack.append(entry)
        self._pending_undo_cb = _undo
        self._update_undo_toast()

    def _update_undo_toast(self) -> None:
        """Refresh the undo toast to reflect current undo stack count."""
        n = len(self._undo_stack)
        if n == 0:
            self._toast.hide()
            # Stop any running auto-hide timer
            if hasattr(self, "_toast_hide_timer"):
                self._toast_hide_timer.stop()
            return

        msg = i18n.get("main.deleted_pending", count=n) if n > 1 else i18n.get("main.deleted_single")
        self._toast._label.setText(msg)
        self._toast._undo_btn.setText("Undo")
        self._toast._undo_btn.show()
        try:
            self._toast._undo_btn.clicked.disconnect()
        except Exception:
            pass
        self._toast._undo_btn.clicked.connect(self._undo_last_delete)
        self._toast.adjustSize()
        pw = self.width()
        self._toast.move((pw - self._toast.width()) // 2, 56)
        self._toast.show()
        self._toast.raise_()

        # Auto-hide: use the longest remaining timer in the stack + 200 ms buffer
        if not hasattr(self, "_toast_hide_timer"):
            self._toast_hide_timer = QTimer(self)
            self._toast_hide_timer.setSingleShot(True)
            self._toast_hide_timer.timeout.connect(self._on_toast_hide_timer)

        # Find remaining time of the entry that expires last
        max_remaining = 0
        for entry in self._undo_stack:
            t = entry.get("timer")
            if t and t.isActive():
                max_remaining = max(max_remaining, t.remainingTime())
        self._toast_hide_timer.stop()
        self._toast_hide_timer.start(max(max_remaining + 200, 500))

    def _on_toast_hide_timer(self) -> None:
        """Called when auto-hide timer fires; hide toast if stack is empty."""
        if not self._undo_stack:
            self._toast.hide()

    def _undo_last_delete(self) -> None:
        """Undo the most recently deleted item."""
        if not self._undo_stack:
            return
        entry = self._undo_stack[-1]  # most recent
        entry["timer"].stop()
        entry["undo_cb"]()            # restores item, removes from stack

    def _flush_undo_stack(self) -> None:
        """Commit all pending deletions immediately (called on window hide)."""
        stack = list(self._undo_stack)
        self._undo_stack.clear()
        for entry in stack:
            entry["timer"].stop()
            entry["commit_cb"]()
        if stack:
            self._toast.hide()

    # ── Multi-select ──────────────────────────────────────────────────────────

    def _enter_select_mode(self) -> None:
        self._select_mode = True
        self._selected_ids.clear()
        self._multiselect_toolbar.setVisible(True)
        self._sel_count_lbl.setText(i18n.get("main.selected_count", count=0))
        for card in self._cards:
            card.set_select_mode(True)
            card.set_selected(False)

    def _exit_select_mode(self) -> None:
        self._select_mode = False
        self._selected_ids.clear()
        self._multiselect_toolbar.setVisible(False)
        for card in self._cards:
            card.set_select_mode(False)

    def _on_card_selection_changed(self, item_id: int, selected: bool) -> None:
        if selected:
            self._selected_ids.add(item_id)
        else:
            self._selected_ids.discard(item_id)
        n = len(self._selected_ids)
        self._sel_count_lbl.setText(i18n.get("main.selected_count", count=n))

    def _multiselect_copy(self) -> None:
        if not self._selected_ids:
            return
        texts   = []
        skipped = 0
        for item in self._all_items:
            if item["id"] in self._selected_ids:
                t = item.get("content_text")
                if t:
                    texts.append(t)
                else:
                    skipped += 1   # image or blob-only item
        if texts:
            from PyQt6.QtWidgets import QApplication as _App
            _App.clipboard().setText("\n".join(texts))
            self._exit_select_mode()
            if skipped:
                self.show_copy_toast(i18n.get("main.multicopy_mixed", copied=len(texts), skipped=skipped))
            else:
                self.show_copy_toast(i18n.get("main.multicopy_done", count=len(texts)))
        elif skipped:
            # All selected items were images — nothing to copy as text
            self._exit_select_mode()
            self._toast.show_message(i18n.get("main.multicopy_images_only"), duration_ms=1200)

    def _multiselect_delete(self) -> None:
        if not self._selected_ids:
            return
        MAX_UNDO = 8
        UNDO_MS  = 3_000

        id_list   = list(self._selected_ids)
        saved_ids = frozenset(id_list)

        # Save deleted items and their positions
        deleted_items = [(i, self._all_items.index(i)) for i in self._all_items if i["id"] in saved_ids]

        # 1. Delete from DB immediately
        if self._db:
            self._db.delete_items(list(saved_ids))

        # 2. Remove from in-memory list and UI
        self._all_items = [i for i in self._all_items if i["id"] not in saved_ids]
        self._pending_deletions.update(saved_ids)
        for iid in saved_ids:
            c = self._card_cache.pop(iid, None)
            if c:
                self._list_layout.removeWidget(c)
                c.setParent(None)

        self._exit_select_mode()
        self._apply_filter(self._search.text())

        stack_key = min(saved_ids)

        def _on_expire() -> None:
            self._pending_deletions.difference_update(saved_ids)
            self._undo_stack = [e for e in self._undo_stack if e.get("item_id") != stack_key]
            self._update_undo_toast()

        def _undo() -> None:
            self._pending_deletions.difference_update(saved_ids)
            self._undo_stack = [e for e in self._undo_stack if e.get("item_id") != stack_key]
            # Re-insert each item to DB and memory
            for item, pos in sorted(deleted_items, key=lambda x: x[1]):
                if self._db:
                    try:
                        self._db.restore_item(item)
                    except Exception:
                        try:
                            self._db.add_item(
                                item.get("content_type", "text"),
                                item.get("size_bytes", 0),
                                content_text=item.get("content_text"),
                                content_blob=item.get("content_blob"),
                                source_app=item.get("source_app"),
                            )
                        except Exception as exc:
                            logger.error("Undo re-insert failed: %s", exc)
                insert_pos = min(pos, len(self._all_items))
                self._all_items.insert(insert_pos, item)
            self._apply_filter(self._search.text())
            self._update_undo_toast()

        expire_timer = QTimer(self)
        expire_timer.setSingleShot(True)
        expire_timer.timeout.connect(_on_expire)
        expire_timer.start(UNDO_MS)

        entry = {"item_id": stack_key, "undo_cb": _undo, "commit_cb": _on_expire, "timer": expire_timer}

        if len(self._undo_stack) >= MAX_UNDO:
            oldest = self._undo_stack.pop(0)
            oldest["timer"].stop()
            oldest["commit_cb"]()

        self._undo_stack.append(entry)
        self._pending_undo_cb = _undo
        self._update_undo_toast()

    # ── Favorites ─────────────────────────────────────────────────────────────

    def _refresh_favorites_panel(self) -> None:
        if self._db is None:
            return
        # Rebuild category buttons
        # Clear old buttons from layout
        while self._fav_cat_layout.count():
            item = self._fav_cat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        categories = self._db.get_favorite_categories()
        default_cats = list(DEFAULT_FAVORITE_CATEGORIES)
        # Only show categories that have entries
        show_cats = [c for c in categories if c in default_cats] + \
                    [c for c in categories if c not in default_cats]

        # "All" button
        all_btn = self._make_cat_button(i18n.get("favorites.all"), self._fav_active_category is None)
        all_btn.clicked.connect(lambda: self._filter_favorites(None))
        self._fav_cat_layout.addWidget(all_btn)

        for cat in show_cats:
            active = self._fav_active_category == cat
            btn = self._make_cat_button(_category_label(cat), active)
            btn.clicked.connect(lambda _, c=cat: self._filter_favorites(c))
            self._fav_cat_layout.addWidget(btn)

        self._fav_cat_layout.addStretch()

        # Manage button (rename/delete categories)
        if show_cats:
            manage_btn = QPushButton(i18n.get("favorites.manage"))
            manage_btn.setFixedHeight(26)
            manage_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            manage_btn.setStyleSheet(f"""
                QPushButton {{ background:transparent; color:{TEXT_DIM}; border:1px solid {BORDER};
                              border-radius:6px; font-family:'Segoe UI',sans-serif;
                              font-size:10px; padding:0 8px; }}
                QPushButton:hover {{ background:{BG_HOVER}; color:{TEXT}; }}
            """)
            manage_btn.clicked.connect(self._manage_categories)
            self._fav_cat_layout.addWidget(manage_btn)

        self._rebuild_favorites_list()

    def _make_cat_button(self, label: str, active: bool) -> QPushButton:
        btn = QPushButton(label)
        btn.setFixedHeight(26)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if active:
            btn.setStyleSheet(f"""
                QPushButton {{ background:{ACCENT}; color:white; border:none; border-radius:6px;
                              font-family:'Segoe UI',sans-serif; font-size:10px;
                              font-weight:700; padding:0 10px; }}
                QPushButton:hover {{ background:#7D75FF; }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{ background:transparent; color:{TEXT_DIM}; border:1px solid {BORDER};
                              border-radius:6px; font-family:'Segoe UI',sans-serif;
                              font-size:10px; font-weight:600; padding:0 10px; }}
                QPushButton:hover {{ background:{BG_HOVER}; color:{TEXT}; border-color:{ACCENT_DIM}; }}
            """)
        return btn

    def _filter_favorites(self, category: str | None) -> None:
        self._fav_active_category = category
        self._refresh_favorites_panel()

    def _rebuild_favorites_list(self) -> None:
        if self._db is None:
            return
        # Clear list — keep the empty-state widget, remove everything else
        to_remove = []
        for idx in range(self._fav_list_layout.count()):
            item = self._fav_list_layout.itemAt(idx)
            if item is None:
                continue
            w = item.widget()
            if w is not None and w is not self._fav_empty_widget:
                to_remove.append(w)
        for w in to_remove:
            self._fav_list_layout.removeWidget(w)
            w.setParent(None)

        favs = self._db.get_favorites(self._fav_active_category)
        query = self._fav_search.text().strip() if hasattr(self, "_fav_search") else ""
        if query:
            favs = [fav for fav in favs if _matches_favorite(fav, query)]

        # Update count label with favorites count
        if self._active_tab == "favorites":
            n = len(favs)
            self._count_lbl.setText(i18n.get("favorites.count", count=n) if n else "")

        if not favs:
            self._fav_empty_widget.setVisible(True)
            return
        self._fav_empty_widget.setVisible(False)

        for fav in favs:
            card = self._make_fav_card(fav)
            self._fav_list_layout.insertWidget(self._fav_list_layout.count() - 1, card)

    def _make_fav_card(self, fav: dict) -> QWidget:
        card = FavoriteItemCard(
            fav,
            db=self._db,
            on_copy=self.show_copy_toast,
            on_item_edited=self._rebuild_favorites_list,
            parent=self,
        )
        card.removed.connect(self._remove_favorite)
        return card

    def _copy_favorite(self, text: str) -> None:
        from PyQt6.QtWidgets import QApplication as _App
        _App.clipboard().setText(text)
        self.show_copy_toast(i18n.get("notifications.copied"))

    def _copy_favorite_image(self, blob: bytes) -> None:
        """Copy a favorite image blob back to the system clipboard."""
        try:
            import io
            from PIL import Image
            from PyQt6.QtGui import QImage, QPixmap
            from PyQt6.QtWidgets import QApplication as _App
            img  = Image.open(io.BytesIO(blob)).convert("RGBA")
            data = img.tobytes("raw", "RGBA")
            qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
            _App.clipboard().setPixmap(QPixmap.fromImage(qimg))
            self.show_copy_toast(i18n.get("notifications.image_copied"))
        except Exception as exc:
            logger.error("Copy favorite image failed: %s", exc)

    def _remove_favorite(self, fav_id: int) -> None:
        if not self._db:
            return
        if confirm(
            self,
            i18n.get("favorites.remove_title"),
            i18n.get("favorites.remove_body"),
            confirm_key="common.yes",
            cancel_key="common.cancel",
            danger=True,
        ):
            self._db.remove_favorite(fav_id)
            self._rebuild_favorites_list()

    def _manage_categories(self) -> None:
        """Simple dialog to rename or delete categories."""
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                      QLabel, QPushButton, QInputDialog,
                                      QScrollArea, QWidget)
        if not self._db:
            return
        categories = self._db.get_favorite_categories()
        if not categories:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(i18n.get("favorites.manage_title"))
        try:
            icon_path = Path(ICON_APP)
            if icon_path.exists():
                dlg.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            pass
        dlg.setMinimumWidth(320)
        dlg.setStyleSheet(f"""
            QDialog {{ background:#1A1D27; color:{TEXT}; font-family:'Segoe UI',sans-serif; }}
            QLabel {{ background:transparent; }}
        """)
        v = QVBoxLayout(dlg)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(8)

        hint = QLabel(i18n.get("favorites.manage_hint"))
        hint.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
        hint.setWordWrap(True)
        v.addWidget(hint)

        for cat in categories:
            row = QWidget()
            row.setStyleSheet(f"background:{BG_CARD}; border-radius:8px;")
            rh = QHBoxLayout(row)
            rh.setContentsMargins(10, 6, 10, 6)
            rh.setSpacing(6)
            lbl = QLabel(cat)
            lbl.setStyleSheet(f"color:{TEXT}; font-size:12px;")
            rh.addWidget(lbl, stretch=1)

            rename_btn = QPushButton(i18n.get("common.rename"))
            rename_btn.setFixedHeight(24)
            rename_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            rename_btn.setStyleSheet(f"""
                QPushButton {{ background:{ACCENT_DIM}; color:{TEXT}; border:none; border-radius:5px;
                              font-size:10px; padding:0 8px; }}
                QPushButton:hover {{ background:{ACCENT}; color:white; }}
            """)
            rename_btn.clicked.connect(lambda _, c=cat: self._rename_category_dialog(c, dlg))
            rh.addWidget(rename_btn)

            del_btn = QPushButton(i18n.get("common.delete"))
            del_btn.setFixedHeight(24)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setStyleSheet(f"""
                QPushButton {{ background:{RED_DIM}; color:#FFB3B3; border:1px solid {RED};
                              border-radius:5px; font-size:10px; padding:0 8px; }}
                QPushButton:hover {{ background:{RED}; color:white; }}
            """)
            del_btn.clicked.connect(lambda _, c=cat: self._delete_category_dialog(c, dlg))
            rh.addWidget(del_btn)
            v.addWidget(row)

        close_btn = QPushButton(i18n.get("common.close"))
        close_btn.setFixedHeight(30)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT}; color:white; border:none; border-radius:7px;
                          font-size:12px; font-weight:700; }}
            QPushButton:hover {{ background:#7D75FF; }}
        """)
        close_btn.clicked.connect(dlg.accept)
        v.addWidget(close_btn)
        dlg.exec()
        self._refresh_favorites_panel()

    def _rename_category_dialog(self, old_name: str, parent_dlg) -> None:
        from PyQt6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(
            parent_dlg,
            i18n.get("favorites.rename_title"),
            i18n.get("favorites.rename_prompt", category=_category_label(old_name)),
        )
        if ok and new_name.strip() and new_name.strip() != old_name:
            self._db.rename_favorite_category(old_name, new_name.strip())
            if self._fav_active_category == old_name:
                self._fav_active_category = new_name.strip()
            parent_dlg.accept()  # close manage dialog, reopen would show stale
            self._refresh_favorites_panel()

    def _delete_category_dialog(self, category: str, parent_dlg) -> None:
        if confirm(
            parent_dlg,
            i18n.get("favorites.delete_title"),
            i18n.get("favorites.delete_body", category=_category_label(category)),
            confirm_key="common.yes",
            cancel_key="common.cancel",
            danger=True,
        ):
            self._db.delete_favorite_category(category)
            if self._fav_active_category == category:
                self._fav_active_category = None
            parent_dlg.accept()
            self._refresh_favorites_panel()

    # ── Drag to move ──────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._header.geometry().contains(event.pos()):
                self._drag_active    = True
                self._drag_start_pos = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_active and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_start_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_active = False
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        # Keep toast centred when window is resized
        if hasattr(self, "_toast"):
            pw = self.width()
            self._toast.move((pw - self._toast.width()) // 2, 56)
        super().resizeEvent(event)

    # ── Events ────────────────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            if self._active_tab == "favorites" and hasattr(self, "_fav_search") and self._fav_search.text():
                self._clear_fav_search()
            elif self._search.text():
                self._clear_search()
            else:
                self.hide_window()
        elif (event.key() == Qt.Key.Key_Z and
              event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            # Ctrl+Z → undo most recent pending delete
            if self._undo_stack:
                self._undo_last_delete()
        else:
            super().keyPressEvent(event)

    def register_sibling_window(self, win) -> None:
        """Register a top-level window that should NOT dismiss the panel."""
        if win not in self._sibling_windows:
            self._sibling_windows.append(win)

    def eventFilter(self, obj, event: QEvent) -> bool:
        # Outside-click-to-close is handled by _OutsideClickFilter on QApplication.
        # This filter only handles app-level clicks to hide when another app is clicked
        # (kept for legacy compatibility — _OutsideClickFilter supersedes it).
        return super().eventFilter(obj, event)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        painter.end()
        super().paintEvent(event)


# ── Quick test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import utils.i18n as i18n
    from core.database import Database
    from utils.config  import DB_PATH, LOCALE_DIR

    logging.basicConfig(level=logging.DEBUG)
    i18n.init(LOCALE_DIR)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    db = Database(db_path=DB_PATH)
    db.init_db()
    if not db.get_all_items():
        db.add_item("text",     7,  content_text="#6C63FF",                      source_app="VS Code")
        db.add_item("link",     50, content_text="https://github.com/anthropics", source_app="github.com")
        db.add_item("text",     44, content_text="Hello from VeilClip!",          source_app="Notepad")

    win = VeilClipWindow(db=db)

    from PyQt6.QtCore import QTimer
    from utils.hotkey import HotkeyManager

    def _safe_toggle():
        QTimer.singleShot(0, win.toggle)

    mgr = HotkeyManager()
    mgr.register("alt+v", _safe_toggle)
    print("Alt+V → toggle | resize from bottom-right corner")
    sys.exit(app.exec())
