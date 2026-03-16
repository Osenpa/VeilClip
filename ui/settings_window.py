"""
ui/settings_window.py
─────────────────────
VeilClip settings dialog.

New in this version
────────────────────
• "Open at cursor" toggle in WINDOW section — controls whether the
  panel always opens at the mouse cursor or at the last saved position.
  Calls on_open_at_cursor_changed(bool) callback → main_window.set_open_at_cursor().
"""

import logging
import sys
import subprocess
from pathlib import Path
from typing import Callable

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore    import Qt
from PyQt6.QtGui     import QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel,
    QPushButton, QSlider, QVBoxLayout, QWidget,
)

import utils.i18n as i18n
from utils.config import (
    APP_NAME,
    APP_VERSION,
    AUTO_DELETE_HOURS,
    AUTO_DELETE_ENABLED,
    CONFIG_FILE,
    ICON_APP,
    LEGACY_CONFIG_FILE,
    LOCALE_DIR,
)
from utils.dialogs import confirm, message
from utils.qt_i18n import translate_labels
from utils.runtime import (
    relaunch_command,
    startup_shortcut_details,
    startup_shortcut_path,
)
from utils.styles import (
    BG, BG_CARD, BG_HOVER,
    ACCENT, ACCENT_DIM, TEXT, TEXT_DIM, BORDER,
    RED, RED_DIM,
    btn_primary, btn_ghost, btn_danger,
)

logger = logging.getLogger(__name__)

# ── Config helpers ────────────────────────────────────────────────────────────

from utils.config_manager import cfg as _cfg


# ── Toggle button ─────────────────────────────────────────────────────────────

class _Toggle(QPushButton):
    def __init__(self, checked: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(52, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh()
        self.toggled.connect(lambda _: self._refresh())

    def _refresh(self) -> None:
        on = self.isChecked()
        self.setText("ON" if on else "OFF")
        self.setStyleSheet(f"""
            QPushButton {{
                background: {'#3DCC6E' if on else '#3A3A4A'};
                color: {'white' if on else '#7B7D8E'};
                border: none; border-radius: 13px;
                font-size: 9px; font-weight: 700;
                font-family: 'Segoe UI', sans-serif;
            }}
            QPushButton:hover {{ background: {'#50DD80' if on else '#4A4A5A'}; }}
        """)


# ── SettingsWindow ────────────────────────────────────────────────────────────

class SettingsWindow(QDialog):

    def __init__(
        self,
        on_hotkey_changed:            Callable[[str], None]       | None = None,
        on_clear_history:             Callable[[], None]           | None = None,
        on_clear_pinned:              Callable[[], None]           | None = None,
        on_cleanup_interval_changed:  Callable[[int, bool], None]  | None = None,
        on_open_at_cursor_changed:    Callable[[bool], None]       | None = None,
        on_close_after_copy_changed:  Callable[[bool], None]       | None = None,
        on_always_on_top_changed:     Callable[[bool], None]       | None = None,
        on_close_on_outside_changed:  Callable[[bool], None]       | None = None,
        on_startup_changed:           Callable[[bool], None]       | None = None,
        db=None,
        vault=None,
        backup_manager=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._on_hotkey_changed       = on_hotkey_changed
        self._on_clear_history        = on_clear_history
        self._on_clear_pinned         = on_clear_pinned
        self._on_cleanup_changed      = on_cleanup_interval_changed
        self._on_open_at_cursor       = on_open_at_cursor_changed
        self._on_close_after_copy     = on_close_after_copy_changed
        self._on_always_on_top        = on_always_on_top_changed
        self._on_close_on_outside     = on_close_on_outside_changed
        self._on_startup              = on_startup_changed
        self._db                      = db
        self._vault                   = vault
        self._backup_manager          = backup_manager
        self._capturing               = False

        cfg = _cfg.all()
        self._current_hotkey     = cfg.get("hotkey",             "alt+v")
        self._auto_delete_hours  = cfg.get("auto_delete_hours",  AUTO_DELETE_HOURS)
        self._auto_delete_on     = cfg.get("auto_delete",        AUTO_DELETE_ENABLED)
        self._open_at_cursor     = cfg.get("open_at_cursor",     False)
        self._close_after_copy   = cfg.get("close_after_copy",   True)
        self._always_on_top           = cfg.get("always_on_top",           True)
        self._close_on_outside        = cfg.get("close_on_outside_click",  False)
        self._startup_enabled         = self._startup_shortcut_is_current()
        self._language_code           = i18n.current_language()
        self._language_buttons: dict[str, QPushButton] = {}
        self._backup_dir_path         = cfg.get("backup_dir", "")

        self.setWindowTitle(i18n.literal("Settings"))
        # Fix 7: set window icon
        try:
            icon_path = Path(ICON_APP)
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            pass
        self.setMinimumSize(720, 560)
        self.resize(800, 680)
        self.setStyleSheet(f"""
            QDialog  {{ background:{BG}; color:{TEXT}; font-family:'Segoe UI',sans-serif; }}
            QLabel   {{ background:transparent; }}
            QSlider::groove:horizontal  {{ background:{BG_HOVER}; height:4px; border-radius:2px; }}
            QSlider::handle:horizontal  {{ background:{ACCENT}; width:16px; height:16px; margin:-6px 0; border-radius:8px; }}
            QSlider::sub-page:horizontal {{ background:{ACCENT}; border-radius:2px; }}
        """)
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        from PyQt6.QtWidgets import QScrollArea, QStackedWidget

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Left sidebar ──────────────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setFixedWidth(148)
        sidebar.setStyleSheet(f"background:{BG_CARD}; border:none;")
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(8, 12, 8, 16)
        sb_layout.setSpacing(2)

        # Section definitions: (label, builder_method)
        # Grouped into three logical categories
        self._sections = [
            ("Languages",   self._section_language),
            ("Hotkey",      self._section_hotkey),
            ("Window",      self._section_window),
            ("History",     self._section_history),
            ("Storage",     self._section_storage),
            ("Backup",      self._section_backup),
            ("Export",      self._section_export),
            ("Locked Notes",  self._section_vault),
            ("Privacy",     self._section_privacy),
            ("About",       self._section_about),
        ]

        # Group definitions: (group_label, list_of_section_indices)
        _GROUPS = [
            ("Basics",           [0, 1, 2]),
            ("Data",             [3, 4, 5, 6]),
            ("Privacy & About",  [7, 8, 9]),
        ]

        # ── Right content area ────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background:{BG};")

        scroll_style = (
            f"QScrollArea{{background:{BG};border:none;}}"
            f"QScrollBar:vertical{{background:{BG_CARD};width:5px;border-radius:3px;}}"
            f"QScrollBar::handle:vertical{{background:{ACCENT};border-radius:3px;min-height:20px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}"
        )

        # Build pages first (order matches self._sections)
        for label, builder in self._sections:
            section_widget = builder()
            translate_labels(section_widget)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setStyleSheet(scroll_style)
            page = QWidget()
            page.setStyleSheet(f"background:{BG};")
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(20, 20, 20, 20)
            page_layout.setSpacing(0)
            page_layout.addWidget(section_widget)
            page_layout.addStretch()
            scroll.setWidget(page)
            self._stack.addWidget(scroll)

        # Build sidebar nav with group headers
        self._nav_btns: list[QPushButton] = [None] * len(self._sections)

        for group_label, section_indices in _GROUPS:
            # Group header label — not clickable, just visual separator
            grp_lbl = QLabel(i18n.literal(group_label).upper())
            grp_lbl.setFixedHeight(22)
            grp_lbl.setStyleSheet(
                f"color:{TEXT_DIM}; font-family:'Segoe UI',sans-serif;"
                f" font-size:9px; font-weight:700; letter-spacing:1px;"
                f" background:transparent; padding-left:6px; border:none;"
            )
            sb_layout.addWidget(grp_lbl)

            for idx in section_indices:
                label = self._sections[idx][0]
                btn = QPushButton(label)
                btn.setFixedHeight(30)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda _, i=idx: self._show_section(i))
                self._nav_btns[idx] = btn
                sb_layout.addWidget(btn)

            # Small gap between groups
            spacer = QWidget()
            spacer.setFixedHeight(6)
            spacer.setStyleSheet("background:transparent;")
            sb_layout.addWidget(spacer)

        sb_layout.addStretch()

        outer.addWidget(sidebar)

        # Thin vertical separator between sidebar and content
        _vsep = QWidget()
        _vsep.setFixedWidth(1)
        _vsep.setStyleSheet(f"background:{BORDER}; border:none;")
        outer.addWidget(_vsep)

        outer.addWidget(self._stack, stretch=1)

        # Show first section (Hotkey) by default
        self._show_section(0)

    def _show_section(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        active_style = (
            f"QPushButton{{background:{ACCENT};color:white;border:none;border-radius:6px;"
            f"font-family:'Segoe UI',sans-serif;font-size:11px;font-weight:700;"
            f"text-align:left;padding:0 10px;}}"
            f"QPushButton:hover{{background:#7D75FF;}}"
        )
        inactive_style = (
            f"QPushButton{{background:transparent;color:{TEXT_DIM};border:none;border-radius:6px;"
            f"font-family:'Segoe UI',sans-serif;font-size:11px;font-weight:500;"
            f"text-align:left;padding:0 10px;}}"
            f"QPushButton:hover{{background:{BG_HOVER};color:{TEXT};}}"
        )
        for i, btn in enumerate(self._nav_btns):
            if btn is not None:
                btn.setStyleSheet(active_style if i == index else inactive_style)

    def _section_language(self) -> QWidget:
        card = self._card()
        lay = QVBoxLayout(card)
        lay.setSpacing(12)
        lay.addWidget(self._title("Languages"))

        info = QLabel(
            "Choose the language used by VeilClip. The app will restart to apply the change everywhere."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
        lay.addWidget(info)

        from PyQt6.QtWidgets import QGridLayout

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        self._language_buttons.clear()
        for idx, lang in enumerate(i18n.available_languages()):
            label = f"{lang['native_name']}\n{lang['name']}"
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(54)
            btn.setStyleSheet(self._language_btn_style(lang["code"] == self._language_code))
            btn.clicked.connect(lambda _, code=lang["code"]: self._change_language(code))
            self._language_buttons[lang["code"]] = btn
            grid.addWidget(btn, idx // 2, idx % 2)

        lay.addLayout(grid)

        note = QLabel("English remains the default fallback if a locale file is missing.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px; font-style:italic;")
        lay.addWidget(note)
        return card

    # ── Hotkey ────────────────────────────────────────────────────────────────

    def _section_hotkey(self) -> QWidget:
        card = self._card()
        lay  = QVBoxLayout(card)
        lay.setSpacing(10)
        lay.addWidget(self._title("Hotkey"))

        row = QHBoxLayout(); row.setSpacing(10)
        self._hotkey_lbl = QLabel(self._current_hotkey.upper())
        self._hotkey_lbl.setStyleSheet(self._hotkey_lbl_style(active=False))
        self._hotkey_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self._hotkey_lbl, stretch=1)

        self._change_btn = QPushButton("Change")
        self._change_btn.setFixedHeight(32)
        self._change_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._change_btn.setStyleSheet(self._btn_style(ACCENT))
        self._change_btn.clicked.connect(self._start_capture)
        row.addWidget(self._change_btn)
        lay.addLayout(row)

        hint = QLabel("Click 'Change', then press your desired key combination.")
        hint.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
        lay.addWidget(hint)

        # ── Separator ─────────────────────────────────────────────────────────
        _sep = QWidget(); _sep.setFixedHeight(1)
        _sep.setStyleSheet(f"background:{BORDER}; border:none;")
        lay.addWidget(_sep)

        # ── Reset to default ──────────────────────────────────────────────────
        reset_lbl = QLabel("The default hotkey is  Alt+V.")
        reset_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
        lay.addWidget(reset_lbl)

        reset_btn = QPushButton("Reset to Default  (Alt+V)")
        reset_btn.setFixedHeight(32)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.setStyleSheet(self._btn_style(ACCENT))
        reset_btn.clicked.connect(self._reset_hotkey)
        lay.addWidget(reset_btn)

        return card

    def _reset_hotkey(self) -> None:
        """Reset the hotkey to the default (alt+v)."""
        default = "alt+v"
        self._current_hotkey = default
        self._hotkey_lbl.setText(default.upper())
        self._hotkey_lbl.setStyleSheet(self._hotkey_lbl_style(active=False))
        _cfg.update({"hotkey": default})
        if self._on_hotkey_changed:
            self._on_hotkey_changed(default)

    # ── Window behaviour ──────────────────────────────────────────────────────

    def _section_window(self) -> QWidget:
        card = self._card()
        lay  = QVBoxLayout(card)
        lay.setSpacing(10)
        lay.addWidget(self._title("Window Behaviour"))

        # ── Open at cursor ────────────────────────────────────────────────────
        row1 = QHBoxLayout()
        lbl1 = QLabel("Always open at mouse cursor\n(OFF = remember last position)")
        lbl1.setStyleSheet(f"color:{TEXT}; font-size:12px;")
        row1.addWidget(lbl1, stretch=1)
        self._cursor_toggle = _Toggle(checked=self._open_at_cursor)
        self._cursor_toggle.toggled.connect(self._on_cursor_toggle)
        row1.addWidget(self._cursor_toggle)
        lay.addLayout(row1)

        note1 = QLabel("When OFF: first open at cursor, then reopens at last closed position.")
        note1.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px; font-style:italic;")
        lay.addWidget(note1)

        # ── Separator ─────────────────────────────────────────────────────────
        sep = QWidget(); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{BORDER};")
        lay.addWidget(sep)

        # ── Close after copy ──────────────────────────────────────────────────
        row2 = QHBoxLayout()
        lbl2 = QLabel("Close panel after copying\n(OFF = panel stays open)")
        lbl2.setStyleSheet(f"color:{TEXT}; font-size:12px;")
        row2.addWidget(lbl2, stretch=1)
        self._copy_close_toggle = _Toggle(checked=self._close_after_copy)
        self._copy_close_toggle.toggled.connect(self._on_copy_close_toggle)
        row2.addWidget(self._copy_close_toggle)
        lay.addLayout(row2)

        note2 = QLabel("When OFF: keep the panel open so you can copy multiple items.")
        note2.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px; font-style:italic;")
        lay.addWidget(note2)

        # ── Separator ─────────────────────────────────────────────────────────
        sep2 = QWidget(); sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background:{BORDER};")
        lay.addWidget(sep2)

        # ── Always on Top ─────────────────────────────────────────────────────
        row3 = QHBoxLayout()
        lbl3 = QLabel("Always on top\n(all VeilClip windows stay above other windows)")
        lbl3.setStyleSheet(f"color:{TEXT}; font-size:12px;")
        row3.addWidget(lbl3, stretch=1)
        self._always_on_top_toggle = _Toggle(checked=self._always_on_top)
        self._always_on_top_toggle.toggled.connect(self._on_always_on_top_toggle)
        row3.addWidget(self._always_on_top_toggle)
        lay.addLayout(row3)

        note3 = QLabel("When ON: VeilClip windows will always appear above every other window.")
        note3.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px; font-style:italic;")
        lay.addWidget(note3)

        # ── Separator ─────────────────────────────────────────────────────────
        sep3 = QWidget(); sep3.setFixedHeight(1)
        sep3.setStyleSheet(f"background:{BORDER};")
        lay.addWidget(sep3)

        # ── Close on outside click ────────────────────────────────────────────
        row4 = QHBoxLayout()
        lbl4 = QLabel("Close panel when clicking outside\n(OFF = panel stays open on outside click)")
        lbl4.setStyleSheet(f"color:{TEXT}; font-size:12px;")
        row4.addWidget(lbl4, stretch=1)
        self._close_outside_toggle = _Toggle(checked=self._close_on_outside)
        self._close_outside_toggle.toggled.connect(self._on_close_outside_toggle)
        row4.addWidget(self._close_outside_toggle)
        lay.addLayout(row4)

        note4 = QLabel("When ON: clicking anywhere outside VeilClip dismisses the panel.")
        note4.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px; font-style:italic;")
        lay.addWidget(note4)

        # ── Separator ─────────────────────────────────────────────────────────
        sep4 = QWidget(); sep4.setFixedHeight(1)
        sep4.setStyleSheet(f"background:{BORDER};")
        lay.addWidget(sep4)

        # ── Run at startup ────────────────────────────────────────────────────
        row5 = QHBoxLayout()
        lbl5 = QLabel("Run at Windows startup\n(launches VeilClip automatically on login)")
        lbl5.setStyleSheet(f"color:{TEXT}; font-size:12px;")
        row5.addWidget(lbl5, stretch=1)
        self._startup_toggle = _Toggle(checked=self._startup_enabled)
        self._startup_toggle.toggled.connect(self._on_startup_toggle)
        row5.addWidget(self._startup_toggle)
        lay.addLayout(row5)

        note5 = QLabel("When ON: VeilClip starts with Windows via your Startup folder shortcut.")
        note5.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px; font-style:italic;")
        lay.addWidget(note5)
        return card

    # ── Storage location ──────────────────────────────────────────────────────

    def _section_storage(self) -> QWidget:
        from utils.config import DB_PATH, APP_DIR
        card = self._card()
        lay  = QVBoxLayout(card)
        lay.setSpacing(10)
        lay.addWidget(self._title("Storage"))

        path_lbl = QLabel(str(DB_PATH))
        path_lbl.setStyleSheet(
            f"color:{ACCENT}; font-family:'Consolas',monospace; font-size:10px; "
            f"background:{BG}; border:1px solid {BORDER}; border-radius:5px; padding:4px 8px;"
        )
        path_lbl.setWordWrap(True)
        path_lbl.setTextInteractionFlags(
            path_lbl.textInteractionFlags() |
            __import__('PyQt6.QtCore', fromlist=['Qt']).Qt.TextInteractionFlag.TextSelectableByMouse
        )
        lay.addWidget(path_lbl)

        btn_row = QHBoxLayout(); btn_row.setSpacing(8)

        open_btn = QPushButton("Open Folder")
        open_btn.setFixedHeight(32)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setStyleSheet(self._btn_style(ACCENT))
        open_btn.clicked.connect(lambda: self._open_data_folder(APP_DIR))
        btn_row.addWidget(open_btn)

        copy_btn = QPushButton("Copy Path")
        copy_btn.setFixedHeight(32)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet(self._btn_style(ACCENT))
        copy_btn.clicked.connect(lambda: (
            __import__('PyQt6.QtWidgets', fromlist=['QApplication']).QApplication.clipboard()
            .setText(str(DB_PATH))
        ))
        btn_row.addWidget(copy_btn)

        change_btn = QPushButton("Change Path")
        change_btn.setFixedHeight(32)
        change_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        change_btn.setStyleSheet(self._btn_style(ACCENT))
        change_btn.clicked.connect(lambda: self._change_db_path(path_lbl))
        btn_row.addWidget(change_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        reset_btn = QPushButton("Reset to Default")
        reset_btn.setFixedHeight(28)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.setStyleSheet(self._btn_style(ACCENT))
        reset_btn.clicked.connect(lambda: self._reset_db_path(path_lbl))
        lay.addWidget(reset_btn)

        note_path = QLabel("Restart VeilClip after changing the database path.")
        note_path.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px; font-style:italic;")
        lay.addWidget(note_path)
        return card

    def _change_db_path(self, path_lbl) -> None:
        """Let the user pick a new folder for the database file."""
        from PyQt6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Database Folder",
            str(Path.home()),
        )
        if not folder:
            return
        new_path = str(Path(folder) / "veilclip_data.db")
        try:
            _cfg.set("db_path", new_path)
            try:
                import importlib, utils.config as _cfg_mod
                importlib.reload(_cfg_mod)
            except Exception:
                pass
            path_lbl.setText(new_path)
            self._msg_info(
                i18n.get("settings.path_changed_title"),
                i18n.get("settings.path_changed_body", path=new_path),
            )
        except Exception as exc:
            logger.error("Change db path failed: %s", exc)

    def _reset_db_path(self, path_lbl) -> None:
        """Remove custom db_path from config, reverting to the default."""
        try:
            _cfg.delete("db_path")
            try:
                import importlib, utils.config as _cfg_mod
                importlib.reload(_cfg_mod)
            except Exception:
                pass
            from utils.config import DATA_DIR
            default = str(DATA_DIR / "data.db")
            path_lbl.setText(default)
            self._msg_info(
                i18n.get("settings.path_reset_title"),
                i18n.get("settings.path_reset_body"),
            )
        except Exception as exc:
            logger.error("Reset db path failed: %s", exc)

    @staticmethod
    def _open_data_folder(path) -> None:
        import subprocess, os
        try:
            folder = str(path)
            if os.path.exists(folder):
                subprocess.Popen(["explorer", folder])
            else:
                # Create and open
                import pathlib
                pathlib.Path(folder).mkdir(parents=True, exist_ok=True)
                subprocess.Popen(["explorer", folder])
        except Exception as exc:
            logger.warning("Could not open folder: %s", exc)

    # ── History / auto-delete ─────────────────────────────────────────────────

    def _section_history(self) -> QWidget:
        card = self._card()
        lay  = QVBoxLayout(card)
        lay.setSpacing(12)
        lay.addWidget(self._title("Auto-Delete History"))

        toggle_row = QHBoxLayout()
        l = QLabel("Enable auto-delete")
        l.setStyleSheet(f"color:{TEXT}; font-size:12px;")
        toggle_row.addWidget(l); toggle_row.addStretch()
        self._auto_toggle = _Toggle(checked=self._auto_delete_on)
        self._auto_toggle.toggled.connect(self._on_auto_toggle)
        toggle_row.addWidget(self._auto_toggle)
        lay.addLayout(toggle_row)

        self._slider_lbl = QLabel(self._slider_text(self._auto_delete_hours))
        self._slider_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px; border:none;")
        lay.addWidget(self._slider_lbl)

        # Scroll-disabled slider subclass
        class _NoScrollSlider(QSlider):
            def wheelEvent(self, e): e.ignore()

        self._slider = _NoScrollSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(1); self._slider.setMaximum(72)
        self._slider.setValue(self._auto_delete_hours)
        self._slider.setEnabled(self._auto_delete_on)
        self._slider.valueChanged.connect(self._on_slider_changed)
        lay.addWidget(self._slider)

        tick_row = QHBoxLayout()
        for t in ("1 h", "12 h", "24 h", "48 h", "72 h"):
            l2 = QLabel(t); l2.setStyleSheet(f"color:{TEXT_DIM}; font-size:9px; border:none;")
            l2.setAlignment(Qt.AlignmentFlag.AlignCenter); tick_row.addWidget(l2)
        lay.addLayout(tick_row)

        pin_note = QLabel("Pinned items are never auto-deleted.")
        pin_note.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px; font-style:italic;")
        lay.addWidget(pin_note)
        return card

    # ── Automatic Backup ──────────────────────────────────────────────────────

    def _section_backup(self) -> QWidget:
        card = self._card()
        lay  = QVBoxLayout(card)
        lay.setSpacing(16)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.addWidget(self._title("Automatic Backup"))

        cfg = _cfg.all()
        saved_dir   = self._backup_dir_path
        saved_hours = cfg.get("backup_hours", 24)
        saved_keep  = cfg.get("backup_keep",  7)

        # ── Backup folder ─────────────────────────────────────────────────────
        folder_lbl = QLabel("Backup Folder")
        folder_lbl.setStyleSheet(f"color:{TEXT}; font-size:12px; font-weight:600;")
        lay.addWidget(folder_lbl)

        self._backup_dir_lbl = QLabel(saved_dir or "Not set — click Choose Folder to pick one")
        self._backup_dir_lbl.setStyleSheet(
            f"color:{ACCENT if saved_dir else TEXT_DIM}; font-size:11px;"
            f"background:{BG}; border:1px solid {BORDER}; border-radius:6px; padding:6px 10px;"
        )
        self._backup_dir_lbl.setWordWrap(True)
        lay.addWidget(self._backup_dir_lbl)

        pick_btn = QPushButton("Choose Folder")
        pick_btn.setFixedHeight(32)
        pick_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pick_btn.setStyleSheet(self._btn_style(ACCENT))
        pick_btn.clicked.connect(self._pick_backup_folder)
        lay.addWidget(pick_btn)

        # ── Separator ─────────────────────────────────────────────────────────
        _s1 = QWidget(); _s1.setFixedHeight(1)
        _s1.setStyleSheet(f"background:{BORDER}; border:none;")
        lay.addWidget(_s1)

        # ── Schedule ──────────────────────────────────────────────────────────
        schedule_lbl = QLabel("Backup Schedule")
        schedule_lbl.setStyleSheet(f"color:{TEXT}; font-size:12px; font-weight:600;")
        lay.addWidget(schedule_lbl)

        lbl_style = f"color:{TEXT}; font-size:12px; font-family:'Segoe UI',sans-serif; background:transparent;"

        def _make_counter(min_val: int, max_val: int, init_val: int):
            """Build a simple - / value / + counter row widget. Returns (container, value_getter)."""
            container = QWidget()
            container.setFixedHeight(32)
            container.setStyleSheet("background:transparent;")
            h = QHBoxLayout(container)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(0)

            btn_style = (
                f"QPushButton {{ background:{BG_HOVER}; color:white; border:1px solid {BORDER};"
                f" font-size:16px; font-weight:700; font-family:'Segoe UI',sans-serif;"
                f" padding:0; min-width:28px; max-width:28px; }}"
                f"QPushButton:hover {{ background:{ACCENT}; border-color:{ACCENT}; }}"
                f"QPushButton:pressed {{ background:{ACCENT_DIM}; }}"
            )
            val_style = (
                f"background:{BG_CARD}; color:{TEXT}; border-top:1px solid {BORDER};"
                f" border-bottom:1px solid {BORDER}; border-left:none; border-right:none;"
                f" font-size:12px; font-family:'Segoe UI',sans-serif;"
                f" min-width:44px; max-width:44px; padding:0 4px;"
            )

            minus_btn = QPushButton("−")
            minus_btn.setFixedSize(28, 32)
            minus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            minus_btn.setStyleSheet(btn_style)

            val_lbl = QLabel(str(init_val))
            val_lbl.setFixedSize(44, 32)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_lbl.setStyleSheet(val_style)
            val_lbl._value = init_val

            plus_btn = QPushButton("+")
            plus_btn.setFixedSize(28, 32)
            plus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            plus_btn.setStyleSheet(btn_style)

            def _dec():
                v = max(min_val, val_lbl._value - 1)
                val_lbl._value = v
                val_lbl.setText(str(v))
            def _inc():
                v = min(max_val, val_lbl._value + 1)
                val_lbl._value = v
                val_lbl.setText(str(v))

            minus_btn.clicked.connect(_dec)
            plus_btn.clicked.connect(_inc)

            h.addWidget(minus_btn)
            h.addWidget(val_lbl)
            h.addWidget(plus_btn)

            def _get_value():
                return val_lbl._value

            return container, _get_value

        # Hours row
        row_hours = QHBoxLayout(); row_hours.setSpacing(10)
        lh1 = QLabel("Back up every")
        lh1.setStyleSheet(lbl_style)
        row_hours.addWidget(lh1)
        hours_widget, self._backup_hours_input = _make_counter(1, 168, saved_hours)
        row_hours.addWidget(hours_widget)
        lh2 = QLabel("hour(s)")
        lh2.setStyleSheet(f"color:{TEXT_DIM}; font-size:12px; font-family:'Segoe UI',sans-serif; background:transparent;")
        row_hours.addWidget(lh2)
        row_hours.addStretch()
        lay.addLayout(row_hours)

        # Keep row
        row_keep = QHBoxLayout(); row_keep.setSpacing(10)
        lk1 = QLabel("Keep the last")
        lk1.setStyleSheet(lbl_style)
        row_keep.addWidget(lk1)
        keep_widget, self._backup_keep_input = _make_counter(1, 30, saved_keep)
        row_keep.addWidget(keep_widget)
        lk2 = QLabel("backup file(s)")
        lk2.setStyleSheet(f"color:{TEXT_DIM}; font-size:12px; font-family:'Segoe UI',sans-serif; background:transparent;")
        row_keep.addWidget(lk2)
        row_keep.addStretch()
        lay.addLayout(row_keep)

        apply_btn = QPushButton("Save Schedule")
        apply_btn.setFixedHeight(32)
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.setStyleSheet(self._btn_style(ACCENT))
        apply_btn.clicked.connect(self._apply_backup_settings)
        lay.addWidget(apply_btn)

        # ── Separator ─────────────────────────────────────────────────────────
        _s2 = QWidget(); _s2.setFixedHeight(1)
        _s2.setStyleSheet(f"background:{BORDER}; border:none;")
        lay.addWidget(_s2)

        # ── Manual backup ─────────────────────────────────────────────────────
        manual_lbl = QLabel("Manual Backup")
        manual_lbl.setStyleSheet(f"color:{TEXT}; font-size:12px; font-weight:600;")
        lay.addWidget(manual_lbl)

        manual_hint = QLabel("Click the button below to create a backup right now.")
        manual_hint.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
        lay.addWidget(manual_hint)

        now_btn = QPushButton("Back Up Now")
        now_btn.setFixedHeight(32)
        now_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        now_btn.setStyleSheet(self._btn_style(ACCENT))
        now_btn.clicked.connect(self._backup_now)
        lay.addWidget(now_btn)

        note = QLabel("Backups are copies of the database file stored in the folder above.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px; font-style:italic;")
        lay.addWidget(note)
        return card

    def _pick_backup_folder(self) -> None:
        from PyQt6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Backup Folder",
            str(Path.home()),
        )
        if not folder:
            return
        self._backup_dir_path = folder
        self._backup_dir_lbl.setText(folder)
        self._backup_dir_lbl.setStyleSheet(
            f"color:{ACCENT};font-size:11px;"
            f"background:{BG};border:1px solid {BORDER};border-radius:5px;padding:3px 8px;"
        )
        self._apply_backup_settings()

    def _apply_backup_settings(self) -> None:
        folder = self._backup_dir_path
        hours = self._backup_hours_input()
        keep  = self._backup_keep_input()
        _cfg.update({"backup_dir": folder, "backup_hours": hours, "backup_keep": keep})
        if self._backup_manager:
            self._backup_manager.update_settings(folder, hours, keep)

    def _backup_now(self) -> None:
        if self._backup_manager:
            ok, msg = self._backup_manager.run_now()
            self._msg_info(i18n.literal("Back Up Now"), msg)
        else:
            self._msg_info(i18n.literal("Back Up Now"), i18n.get("settings.backup_manager_unavailable"))

    # ── Vault ─────────────────────────────────────────────────────────────────

    # ── Locked Notes (Vault) ──────────────────────────────────────────────────

    def _section_vault(self) -> QWidget:
        card = self._card()
        lay  = QVBoxLayout(card)
        lay.setSpacing(8)
        lay.addWidget(self._title("Locked Notes"))

        info = QLabel(
            "A PIN-protected, encrypted space for passwords and private information.\n"
            "Locked notes are never visible in the main clipboard list."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{TEXT_DIM};font-size:11px;")
        lay.addWidget(info)

        open_btn = QPushButton("Open Locked Notes")
        open_btn.setFixedHeight(32)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setStyleSheet(self._btn_style(ACCENT))
        open_btn.clicked.connect(self._open_vault)
        lay.addWidget(open_btn)
        return card

    def _open_vault(self) -> None:
        if self._vault is None:
            self._msg_info("Vault", "Vault not initialised.")
            return
        from ui.vault_window import VaultWindow
        dlg = VaultWindow(self._vault, parent=self)
        dlg.exec()

    # ── Export / Import ───────────────────────────────────────────────────────

    def _section_export(self) -> QWidget:
        card = self._card()
        lay  = QVBoxLayout(card)
        lay.setSpacing(8)
        lay.addWidget(self._title("Export / Import"))

        info = QLabel(
            "Export clipboard history to JSON or CSV for backup or transfer to another machine.\n"
            "Import merges items into the current history (duplicates are skipped)."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{TEXT_DIM};font-size:11px;")
        lay.addWidget(info)

        row1 = QHBoxLayout()
        exp_json = QPushButton("Export JSON")
        exp_json.setFixedHeight(30)
        exp_json.setCursor(Qt.CursorShape.PointingHandCursor)
        exp_json.setStyleSheet(self._btn_style(ACCENT))
        exp_json.clicked.connect(lambda: self._do_export("json"))
        row1.addWidget(exp_json)

        exp_csv = QPushButton("Export CSV")
        exp_csv.setFixedHeight(30)
        exp_csv.setCursor(Qt.CursorShape.PointingHandCursor)
        exp_csv.setStyleSheet(self._btn_style(ACCENT))
        exp_csv.clicked.connect(lambda: self._do_export("csv"))
        row1.addWidget(exp_csv)
        row1.addStretch()
        lay.addLayout(row1)

        row2 = QHBoxLayout()
        imp_json = QPushButton("Import JSON")
        imp_json.setFixedHeight(30)
        imp_json.setCursor(Qt.CursorShape.PointingHandCursor)
        imp_json.setStyleSheet(self._btn_style("#336655"))
        imp_json.clicked.connect(lambda: self._do_import("json"))
        row2.addWidget(imp_json)

        imp_csv = QPushButton("Import CSV")
        imp_csv.setFixedHeight(30)
        imp_csv.setCursor(Qt.CursorShape.PointingHandCursor)
        imp_csv.setStyleSheet(self._btn_style("#336655"))
        imp_csv.clicked.connect(lambda: self._do_import("csv"))
        row2.addWidget(imp_csv)
        row2.addStretch()
        lay.addLayout(row2)
        return card

    def _do_export(self, fmt: str) -> None:
        if self._db is None:
            self._msg_info(i18n.literal("Export"), i18n.get("settings.database_unavailable"))
            return
        from PyQt6.QtWidgets import QFileDialog
        from pathlib import Path as _P
        filter_str = "JSON files (*.json)" if fmt == "json" else "CSV files (*.csv)"
        path, _ = QFileDialog.getSaveFileName(
            self,
            i18n.get("settings.export_as", format=fmt.upper()),
            f"veilclip_export.{fmt}",
            filter_str,
        )
        if not path:
            return
        from core.exporter import export_json, export_csv
        fn = export_json if fmt == "json" else export_csv
        count, msg = fn(self._db, _P(path))
        self._msg_info(i18n.literal("Export"), msg)

    def _do_import(self, fmt: str) -> None:
        if self._db is None:
            self._msg_info(i18n.literal("Import"), i18n.get("settings.database_unavailable"))
            return
        from PyQt6.QtWidgets import QFileDialog
        from pathlib import Path as _P
        filter_str = "JSON files (*.json)" if fmt == "json" else "CSV files (*.csv)"
        path, _ = QFileDialog.getOpenFileName(
            self,
            i18n.get("settings.import_file", format=fmt.upper()),
            "",
            filter_str,
        )
        if not path:
            return
        from core.exporter import import_json, import_csv
        fn = import_json if fmt == "json" else import_csv
        count, msg = fn(self._db, _P(path))
        self._msg_info(i18n.literal("Import"), msg)

    # ── Privacy ───────────────────────────────────────────────────────────────

    def _section_privacy(self) -> QWidget:
        card = self._card()
        lay  = QVBoxLayout(card)
        lay.setSpacing(10)
        lay.addWidget(self._title("Privacy"))

        row = QHBoxLayout(); row.setSpacing(10)
        b1 = QPushButton("Clear All History")
        b1.setFixedHeight(34); b1.setCursor(Qt.CursorShape.PointingHandCursor)
        b1.setStyleSheet(self._btn_style(RED, RED_DIM, "#FFB3B3"))
        b1.clicked.connect(self._clear_all)
        row.addWidget(b1)

        b2 = QPushButton("Clear Pinned")
        b2.setFixedHeight(34); b2.setCursor(Qt.CursorShape.PointingHandCursor)
        b2.setStyleSheet(self._btn_style("#AA6622","#3A2200","#FFD080"))
        b2.clicked.connect(self._clear_pinned)
        row.addWidget(b2)
        lay.addLayout(row)

        # ── Separator ─────────────────────────────────────────────────────────
        _sep = QWidget(); _sep.setFixedHeight(1)
        _sep.setStyleSheet(f"background:{BORDER}; border:none;")
        lay.addWidget(_sep)

        # ── Reset App ─────────────────────────────────────────────────────────
        reset_title = QLabel("Reset App")
        reset_title.setStyleSheet(f"color:{TEXT}; font-size:12px; font-weight:600;")
        lay.addWidget(reset_title)

        reset_hint = QLabel(
            "This will delete everything — all clipboard history, favorites, "
            "locked notes, settings, and temporary files — then restart VeilClip fresh."
        )
        reset_hint.setWordWrap(True)
        reset_hint.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
        lay.addWidget(reset_hint)

        reset_btn = QPushButton("Reset Everything")
        reset_btn.setFixedHeight(34)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.setStyleSheet(self._btn_style(RED, RED_DIM, "#FFB3B3"))
        reset_btn.clicked.connect(self._reset_app)
        lay.addWidget(reset_btn)

        return card

    def _reset_app(self) -> None:
        """Delete all app data and restart the process."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

        dlg = QDialog(self)
        dlg.setWindowTitle("Reset Everything")
        try:
            icon_path = Path(ICON_APP)
            if icon_path.exists():
                dlg.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            pass
        dlg.setMinimumWidth(420)
        dlg.setStyleSheet(f"""
            QDialog {{ background:{BG}; color:{TEXT}; font-family:'Segoe UI',sans-serif; }}
            QLabel  {{ background:transparent; color:{TEXT}; }}
        """)

        v = QVBoxLayout(dlg)
        v.setContentsMargins(24, 20, 24, 20)
        v.setSpacing(14)

        title_lbl = QLabel("Are you sure?")
        title_lbl.setStyleSheet(f"color:{TEXT}; font-size:14px; font-weight:700;")
        v.addWidget(title_lbl)

        body_lbl = QLabel(
            "This will permanently delete ALL data:\n\n"
            "   \u2022  All clipboard history\n"
            "   \u2022  All favorites\n"
            "   \u2022  All locked notes\n"
            "   \u2022  All settings\n"
            "   \u2022  All temporary files\n\n"
            "VeilClip will restart after the reset.\n"
            "This cannot be undone."
        )
        body_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:12px;")
        body_lbl.setWordWrap(True)
        v.addWidget(body_lbl)

        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(34)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(self._btn_style(BORDER, BORDER, TEXT))
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel_btn)

        confirm_btn = QPushButton("Yes, Reset Everything")
        confirm_btn.setFixedHeight(34)
        confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        confirm_btn.setStyleSheet(self._btn_style(RED, RED_DIM, "#FFB3B3"))
        confirm_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(confirm_btn)

        v.addLayout(btn_row)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        import shutil, os, sys

        # ── Step 1: wipe DB tables via live connection ────────────────────────
        if self._db is not None:
            try:
                # Use raw SQL to nuke everything — fastest and most complete
                with self._db._cursor() as (con, cur):
                    cur.execute("DELETE FROM clipboard_items")
                    try: cur.execute("DELETE FROM clips_fts")
                    except Exception: pass
                    try: cur.execute("DELETE FROM favorites")
                    except Exception: pass
                    try: cur.execute("DELETE FROM vault_items")
                    except Exception: pass
                    try: cur.execute("VACUUM")
                    except Exception: pass
            except Exception as exc:
                logger.warning("DB wipe failed: %s", exc)
            # Close connection so the file can be deleted afterwards
            try: self._db.close()
            except Exception: pass

        # ── Step 2: delete files and directories ─────────────────────────────
        try:
            from utils.config import DATA_DIR, APP_DIR, DB_PATH
        except Exception as exc:
            logger.error("Config import failed during reset: %s", exc)
            QApplication.instance().quit()
            return

        delete_targets = []

        # Database file (in case SQL wipe didn't fully clean WAL files)
        try:
            db_p = Path(str(DB_PATH))
            for suffix in ("", "-wal", "-shm"):
                candidate = Path(str(db_p) + suffix) if suffix else db_p
                delete_targets.append(candidate)
        except Exception:
            pass

        # Entire data and log directories
        try: delete_targets.append(Path(str(DATA_DIR)))
        except Exception: pass
        try:
            from utils.config import LOG_DIR
            delete_targets.append(Path(str(LOG_DIR)))
        except Exception: pass

        # Config JSON (project root)
        try:
            from utils.config_manager import cfg as _c
            if hasattr(_c, '_path'):
                delete_targets.append(Path(_c._path))
        except Exception:
            pass
        # Also remove the legacy source-tree config file if it exists.
        try:
            root_cfg = Path(LEGACY_CONFIG_FILE)
            if root_cfg.exists() and root_cfg not in delete_targets:
                delete_targets.append(root_cfg)
        except Exception:
            pass

        # __pycache__ directories
        try:
            for root_p, dirs, _files in os.walk(str(APP_DIR)):
                for d in dirs:
                    if d == "__pycache__":
                        delete_targets.append(Path(root_p) / d)
        except Exception:
            pass

        for target in delete_targets:
            try:
                if target.is_dir():
                    shutil.rmtree(str(target), ignore_errors=True)
                elif target.is_file():
                    target.unlink(missing_ok=True)
            except Exception as exc:
                logger.warning("Could not delete %s: %s", target, exc)

        # ── Step 3: write a fresh config.json with first_run=True ────────────
        # This makes VeilClip behave exactly like a first-time installation:
        # the welcome banner will appear and the window will auto-open.
        try:
            import json as _json
            fresh_config = {"first_run": True}
            root_cfg = Path(CONFIG_FILE)
            root_cfg.parent.mkdir(parents=True, exist_ok=True)
            root_cfg.write_text(_json.dumps(fresh_config, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not write fresh config: %s", exc)

        # ── Step 4: restart the process ───────────────────────────────────────
        try:
            import subprocess
            subprocess.Popen(relaunch_command())
        except Exception as exc:
            logger.error("Restart failed: %s", exc)
        finally:
            QApplication.instance().quit()

    # ── About ─────────────────────────────────────────────────────────────────

    def _section_about(self) -> QWidget:
        card = self._card()
        lay  = QVBoxLayout(card)
        lay.setSpacing(6)
        lay.addWidget(self._title("About"))
        for txt in (
            f"<b>{APP_NAME}</b>  v{APP_VERSION}",
            "The Stealth &amp; Offline Clipboard for Windows.",
            "Built with Python + PyQt6.",
        ):
            l = QLabel(txt); l.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
            l.setTextFormat(Qt.TextFormat.RichText); lay.addWidget(l)

        sep = QWidget(); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{BORDER}; border:none;")
        lay.addWidget(sep)

        contact_lbl = QLabel("osenpa.com  ·  osenpacom@gmail.com")
        contact_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px;")
        lay.addWidget(contact_lbl)
        return card

    # ── Hotkey capture ────────────────────────────────────────────────────────

    def _start_capture(self) -> None:
        self._capturing = True
        self._hotkey_lbl.setText("Press keys…")
        self._hotkey_lbl.setStyleSheet(self._hotkey_lbl_style(active=True))
        self._change_btn.setText("Cancel")
        self._change_btn.clicked.disconnect()
        self._change_btn.clicked.connect(self._cancel_capture)
        self.setFocus()

    def _cancel_capture(self) -> None:
        self._capturing = False
        self._hotkey_lbl.setText(self._current_hotkey.upper())
        self._hotkey_lbl.setStyleSheet(self._hotkey_lbl_style(active=False))
        self._change_btn.setText("Change")
        self._change_btn.clicked.disconnect()
        self._change_btn.clicked.connect(self._start_capture)

    def keyPressEvent(self, event) -> None:
        if not self._capturing:
            super().keyPressEvent(event); return
        key  = event.key()
        mods = event.modifiers()
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Alt,
                   Qt.Key.Key_Shift,   Qt.Key.Key_Meta,
                   Qt.Key.Key_Escape):
            return
        parts = []
        if mods & Qt.KeyboardModifier.ControlModifier: parts.append("ctrl")
        if mods & Qt.KeyboardModifier.AltModifier:     parts.append("alt")
        if mods & Qt.KeyboardModifier.ShiftModifier:   parts.append("shift")
        key_name = QKeySequence(key).toString().lower()
        if not key_name: return
        parts.append(key_name)
        hotkey = "+".join(parts)
        self._current_hotkey = hotkey
        self._hotkey_lbl.setText(hotkey.upper())
        self._hotkey_lbl.setStyleSheet(self._hotkey_lbl_style(active=False))
        self._capturing = False
        self._change_btn.setText("Change")
        self._change_btn.clicked.disconnect()
        self._change_btn.clicked.connect(self._start_capture)
        _cfg.update({"hotkey": hotkey})
        if self._on_hotkey_changed:
            self._on_hotkey_changed(hotkey)

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _on_cursor_toggle(self, state: bool) -> None:
        self._open_at_cursor = state
        _cfg.update({"open_at_cursor": state})
        if self._on_open_at_cursor:
            self._on_open_at_cursor(state)
        logger.info("open_at_cursor = %s", state)

    def _on_copy_close_toggle(self, state: bool) -> None:
        self._close_after_copy = state
        _cfg.update({"close_after_copy": state})
        if self._on_close_after_copy:
            self._on_close_after_copy(state)
        logger.info("close_after_copy = %s", state)

    def _on_close_outside_toggle(self, state: bool) -> None:
        self._close_on_outside = state
        _cfg.update({"close_on_outside_click": state})
        if self._on_close_on_outside:
            self._on_close_on_outside(state)
        logger.info("close_on_outside_click = %s", state)

    def _on_always_on_top_toggle(self, state: bool) -> None:
        self._always_on_top = state
        _cfg.update({"always_on_top": state})
        if self._on_always_on_top:
            self._on_always_on_top(state)
        logger.info("always_on_top = %s", state)

    def _change_language(self, language_code: str) -> None:
        if language_code == self._language_code:
            return
        label = i18n.language_name(language_code, native=True)
        if not self._msg_confirm(
            i18n.get("language.change_title"),
            i18n.get("language.change_body", language=label),
        ):
            return
        _cfg.set("language", language_code)
        self._restart_application()

    @staticmethod
    def _restart_application() -> None:
        subprocess.Popen(relaunch_command(args=["--show-window"]))
        QApplication.instance().quit()

    # ── Startup helpers ───────────────────────────────────────────────────

    @classmethod
    def _startup_shortcut_file(cls) -> Path:
        return startup_shortcut_path(APP_NAME)

    @classmethod
    def _startup_shortcut_exists(cls) -> bool:
        return cls._startup_shortcut_file().exists()

    @classmethod
    def _startup_shortcut_is_current(cls) -> bool:
        shortcut_path = cls._startup_shortcut_file()
        if not shortcut_path.exists():
            return False
        try:
            from win32com.client import Dispatch

            shell = Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(str(shortcut_path))
            target, arguments, _ = startup_shortcut_details()
            current_target = str(getattr(shortcut, "TargetPath", "") or "").strip()
            current_arguments = str(getattr(shortcut, "Arguments", "") or "").strip()
            return current_target == target and current_arguments == arguments
        except Exception:
            return False

    @classmethod
    def _write_startup_shortcut(cls, enabled: bool) -> bool:
        shortcut_path = cls._startup_shortcut_file()
        try:
            if enabled:
                from win32com.client import Dispatch

                shortcut_path.parent.mkdir(parents=True, exist_ok=True)
                target, arguments, working_dir = startup_shortcut_details()
                shell = Dispatch("WScript.Shell")
                shortcut = shell.CreateShortCut(str(shortcut_path))
                shortcut.TargetPath = target
                shortcut.Arguments = arguments
                shortcut.WorkingDirectory = working_dir
                shortcut.IconLocation = target
                shortcut.Save()
            else:
                shortcut_path.unlink(missing_ok=True)
            return True
        except Exception as exc:
            logger.warning("Startup shortcut update failed: %s", exc)
            return False

    def _on_startup_toggle(self, state: bool) -> None:
        self._startup_enabled = state
        ok = self._write_startup_shortcut(state)
        if not ok:
            self._msg_info(
                i18n.get("settings.startup_error_title"),
                i18n.get("settings.startup_error_body"),
            )
            self._startup_enabled = not state
            self._startup_toggle.setChecked(not state)
        else:
            if self._on_startup:
                self._on_startup(state)
            logger.info("startup = %s", state)

    def _on_slider_changed(self, value: int) -> None:
        self._auto_delete_hours = value
        if hasattr(self, '_slider_lbl'):
            self._slider_lbl.setText(self._slider_text(value))
        _cfg.update({"auto_delete_hours": value, "auto_delete": self._auto_delete_on})
        if self._on_cleanup_changed:
            self._on_cleanup_changed(value, self._auto_delete_on)

    def _on_auto_toggle(self, state: bool) -> None:
        self._auto_delete_on = state
        self._slider.setEnabled(state)
        _cfg.update({"auto_delete": state, "auto_delete_hours": self._auto_delete_hours})
        if self._on_cleanup_changed:
            self._on_cleanup_changed(self._auto_delete_hours, state)

    # ── Styled message helpers (replaces QMessageBox which shows black text on Windows) ──

    def _msg_info(self, title: str, text: str) -> None:
        message(self, title, text)

    def _msg_confirm(self, title: str, text: str) -> bool:
        return confirm(self, title, text)

    def _clear_all(self) -> None:
        if self._msg_confirm(
            i18n.get("settings.clear_history_title"),
            i18n.get("settings.clear_history_body"),
        ):
            if self._on_clear_history:
                self._on_clear_history()

    def _clear_pinned(self) -> None:
        if self._msg_confirm(
            i18n.get("settings.clear_pinned_title"),
            i18n.get("settings.clear_pinned_body"),
        ):
            if self._on_clear_pinned:
                self._on_clear_pinned()

    # ── Widget helpers ────────────────────────────────────────────────────────

    def _card(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{BG_CARD}; border:none; border-radius:10px;")
        return w

    def _title(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(f"color:{TEXT}; font-size:12px; font-weight:700; border:none; padding:4px 0 2px 0;")
        return l

    @staticmethod
    def _slider_text(hours: int) -> str:
        if hours < 24:
            return i18n.get("settings.auto_delete_hours_label", count=hours)
        d = hours/24
        return i18n.get("settings.auto_delete_days_label", count=f"{d:.1f}")

    @staticmethod
    def _hotkey_lbl_style(active: bool) -> str:
        border = f"1px dashed {ACCENT}" if active else f"1px solid {BORDER}"
        color  = TEXT if active else ACCENT
        return (f"color:{color}; background:{BG_HOVER}; border:{border}; border-radius:6px;"
                f"padding:4px 12px; font-size:13px; font-weight:700; font-family:'Consolas',monospace;")

    @staticmethod
    def _language_btn_style(active: bool) -> str:
        if active:
            return (
                f"QPushButton{{background:{ACCENT}; color:white; border:1px solid {ACCENT};"
                f"border-radius:10px; padding:8px 12px; font-family:'Segoe UI',sans-serif;"
                f"font-size:11px; font-weight:700; text-align:left;}}"
                f"QPushButton:hover{{background:#7D75FF;}}"
            )
        return (
            f"QPushButton{{background:{BG}; color:{TEXT}; border:1px solid {BORDER};"
            f"border-radius:10px; padding:8px 12px; font-family:'Segoe UI',sans-serif;"
            f"font-size:11px; font-weight:600; text-align:left;}}"
            f"QPushButton:hover{{background:{BG_HOVER}; border-color:{ACCENT_DIM};}}"
        )

    @staticmethod
    def _btn_style(bg: str, bg_dim: str = "", fg: str = "white") -> str:
        dim = bg_dim or bg+"CC"
        return (f"QPushButton{{background:{dim}; color:{fg}; border:1px solid {bg};"
                f"border-radius:7px; padding:4px 14px; font-family:'Segoe UI',sans-serif;"
                f"font-size:12px; font-weight:600;}}"
                f"QPushButton:hover{{background:{bg}; color:white;}}")


# ── Quick test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import utils.i18n as i18n
    logging.basicConfig(level=logging.DEBUG)
    i18n.init(LOCALE_DIR)
    app = QApplication(sys.argv)
    win = SettingsWindow(
        on_hotkey_changed=lambda h:       print(f"hotkey → {h}"),
        on_clear_history=lambda:          print("clear history"),
        on_clear_pinned=lambda:           print("clear pinned"),
        on_cleanup_interval_changed=lambda h,e: print(f"cleanup {h}h enabled={e}"),
        on_open_at_cursor_changed=lambda v:     print(f"open_at_cursor={v}"),
    )
    win.show()
    sys.exit(app.exec())
