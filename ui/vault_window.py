"""
ui/vault_window.py
──────────────────
Encrypted vault dialog for VeilClip.

Flow
────
• First open  → set PIN dialog
• Subsequent  → enter PIN to unlock
• Once open   → list of vault items with label + masked content
  - Add item:  paste from current clipboard or type manually
  - Copy:      copies decrypted text to clipboard
  - Delete:    removes item (no undo)
• Change PIN button always visible

Design: no icons/emojis, matches VeilClip dark theme.
"""

import logging
import time
from pathlib import Path

from PyQt6.QtCore    import Qt, QTimer
from PyQt6.QtGui     import QIcon
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget, QApplication,
)

from core.vault import VaultManager
import utils.i18n as i18n
from utils.config import ICON_APP
from utils.dialogs import confirm, message, prompt_text

logger = logging.getLogger(__name__)

# ── Palette (matches main theme) ──────────────────────────────────────────────
BG       = "#0F1117"
BG_CARD  = "#1A1D27"
BG_HOVER = "#22263A"
ACCENT   = "#6C63FF"
ACCENT_DIM = "#3D3880"
TEXT     = "#E8E8F0"
TEXT_DIM = "#7B7D8E"
BORDER   = "#2A2D3E"
RED      = "#FF4C4C"
RED_DIM  = "#4A1515"
GREEN    = "#3DCC6E"


def _btn(label: str, bg: str, fg: str = "white", border: str = "") -> QPushButton:
    b = QPushButton(label)
    b.setFixedHeight(28)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    bd = f"border:1px solid {border};" if border else "border:none;"
    b.setStyleSheet(
        f"QPushButton{{background:{bg};color:{fg};{bd}border-radius:6px;"
        f"font-family:'Segoe UI',sans-serif;font-size:11px;font-weight:600;padding:0 12px;}}"
        f"QPushButton:hover{{background:{ACCENT};color:white;}}"
    )
    return b


class VaultWindow(QDialog):

    def __init__(self, vault: VaultManager, parent=None) -> None:
        super().__init__(parent)
        self._vault = vault
        self.setWindowTitle(i18n.get("vault.window_title"))
        self.setMinimumSize(620, 620)
        self.resize(680, 720)
        try:
            p = Path(ICON_APP)
            if p.exists():
                self.setWindowIcon(QIcon(str(p)))
        except Exception:
            pass
        self.setStyleSheet(
            f"QDialog{{background:{BG};color:{TEXT};font-family:'Segoe UI',sans-serif;}}"
            f"QLabel{{background:transparent;}}"
            f"QLineEdit{{background:{BG_CARD};color:{TEXT};border:1px solid {BORDER};"
            f"border-radius:6px;padding:4px 8px;font-size:12px;}}"
            f"QScrollArea{{background:transparent;border:none;}}"
            f"QScrollBar:vertical{{background:{BG_CARD};width:5px;border-radius:3px;}}"
            f"QScrollBar::handle:vertical{{background:{ACCENT_DIM};border-radius:3px;min-height:20px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}"
        )
        self._shown: dict[int, bool] = {}   # vault item show/hide state
        self._failed_attempts  = 0           # wrong PIN counter
        self._locked_until     = 0.0         # epoch time when lockout ends
        self._build_ui()
        # Show appropriate view
        if not self._vault.has_pin():
            self._show_setup_view()
        elif self._vault.is_unlocked():
            self._show_items_view()
        else:
            self._show_unlock_view()

    # ── Layout skeleton ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(20, 18, 20, 18)
        self._root.setSpacing(10)
        self._content_widget: QWidget | None = None

    def _replace_content(self, widget: QWidget) -> None:
        if self._content_widget is not None:
            self._root.removeWidget(self._content_widget)
            self._content_widget.deleteLater()
        self._content_widget = widget
        self._root.addWidget(widget)

    # ── Setup PIN view ────────────────────────────────────────────────────────

    def _show_setup_view(self) -> None:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)

        title = QLabel(i18n.get("vault.set_pin_title"))
        title.setStyleSheet(f"color:{TEXT};font-size:14px;font-weight:700;")
        v.addWidget(title)

        info = QLabel(
            i18n.get("vault.set_pin_desc")
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{TEXT_DIM};font-size:11px;")
        v.addWidget(info)

        self._pin1 = QLineEdit()
        self._pin1.setPlaceholderText("PIN / passphrase")
        self._pin1.setEchoMode(QLineEdit.EchoMode.Password)
        v.addWidget(self._pin1)

        self._pin2 = QLineEdit()
        self._pin2.setPlaceholderText("Confirm PIN")
        self._pin2.setEchoMode(QLineEdit.EchoMode.Password)
        v.addWidget(self._pin2)

        self._setup_err = QLabel("")
        self._setup_err.setStyleSheet(f"color:{RED};font-size:11px;")
        v.addWidget(self._setup_err)

        confirm_btn = _btn(i18n.get("vault.set_pin_action"), ACCENT)
        confirm_btn.clicked.connect(self._do_setup)
        v.addWidget(confirm_btn)
        v.addStretch()
        self._replace_content(w)
        self._pin1.setFocus()

    def _do_setup(self) -> None:
        p1 = self._pin1.text()
        p2 = self._pin2.text()
        if not p1:
            self._setup_err.setText(i18n.get("vault.errors.pin_empty"))
            return
        if p1 != p2:
            self._setup_err.setText(i18n.get("vault.errors.pin_mismatch"))
            return
        self._vault.setup_pin(p1)
        self._show_items_view()

    # ── Unlock view ───────────────────────────────────────────────────────────

    def _show_unlock_view(self) -> None:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)

        title = QLabel(i18n.get("vault.enter_pin"))
        title.setStyleSheet(f"color:{TEXT};font-size:14px;font-weight:700;")
        v.addWidget(title)

        self._unlock_input = QLineEdit()
        self._unlock_input.setPlaceholderText("PIN / passphrase")
        self._unlock_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._unlock_input.returnPressed.connect(self._do_unlock)
        v.addWidget(self._unlock_input)

        self._unlock_err = QLabel("")
        self._unlock_err.setStyleSheet(f"color:{RED};font-size:11px;")
        v.addWidget(self._unlock_err)

        row = QHBoxLayout()
        unlock_btn = _btn(i18n.get("vault.unlock_action"), ACCENT)
        unlock_btn.clicked.connect(self._do_unlock)
        row.addWidget(unlock_btn)
        row.addStretch()
        v.addLayout(row)
        v.addStretch()
        self._replace_content(w)
        self._unlock_input.setFocus()

    def _do_unlock(self) -> None:
        import time as _time

        # Check lockout
        now = _time.time()
        if now < self._locked_until:
            remaining = int(self._locked_until - now) + 1
            self._unlock_err.setText(i18n.get("vault.errors.try_again_in", seconds=remaining))
            self._unlock_input.clear()
            return

        pin = self._unlock_input.text()
        if self._vault.unlock(pin):
            self._failed_attempts = 0
            self._locked_until    = 0.0
            self._show_items_view()
        else:
            self._failed_attempts += 1
            self._unlock_input.clear()
            self._unlock_input.setFocus()

            _MAX   = 5
            _DELAY = 30   # seconds

            if self._failed_attempts >= _MAX:
                self._locked_until = _time.time() + _DELAY
                self._unlock_err.setText(
                    i18n.get("vault.errors.locked_for", seconds=_DELAY)
                )
                # Auto-refresh the message every second so the countdown updates
                QTimer.singleShot(1000, self._refresh_lockout_message)
            else:
                left = _MAX - self._failed_attempts
                self._unlock_err.setText(i18n.get("vault.errors.incorrect_pin", count=left))

    def _refresh_lockout_message(self) -> None:
        """Called every second during lockout to update the countdown label."""
        import time as _time
        if not hasattr(self, "_unlock_err"):
            return
        remaining = self._locked_until - _time.time()
        if remaining > 0:
            self._unlock_err.setText(i18n.get("vault.errors.try_again_in", seconds=int(remaining) + 1))
            QTimer.singleShot(1000, self._refresh_lockout_message)
        else:
            self._failed_attempts = 0
            self._locked_until    = 0.0
            self._unlock_err.setText("")

    # ── Items view ────────────────────────────────────────────────────────────

    def _show_items_view(self) -> None:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(8)

        # Header row
        hdr = QHBoxLayout()
        title = QLabel(i18n.get("vault.main_title"))
        title.setStyleSheet(f"color:{TEXT};font-size:14px;font-weight:700;")
        hdr.addWidget(title)
        hdr.addStretch()

        lock_btn = _btn(i18n.get("vault.lock_action"), BG_HOVER, TEXT_DIM, BORDER)
        lock_btn.clicked.connect(self._do_lock)
        hdr.addWidget(lock_btn)

        change_btn = _btn(i18n.get("vault.change_pin_action"), BG_HOVER, TEXT_DIM, BORDER)
        change_btn.clicked.connect(self._do_change_pin)
        hdr.addWidget(change_btn)
        v.addLayout(hdr)

        # Add item row
        add_row = QHBoxLayout()
        self._new_label = QLineEdit()
        self._new_label.setPlaceholderText("Label  (e.g. GitHub token)")
        add_row.addWidget(self._new_label, stretch=1)

        self._new_content = QLineEdit()
        self._new_content.setPlaceholderText("Secret text")
        self._new_content.setEchoMode(QLineEdit.EchoMode.Password)
        add_row.addWidget(self._new_content, stretch=2)

        add_btn = _btn(i18n.get("common.add"), GREEN)
        add_btn.clicked.connect(self._do_add)
        add_row.addWidget(add_btn)

        paste_btn = _btn(i18n.get("vault.paste_action"), ACCENT_DIM, TEXT, BORDER)
        paste_btn.clicked.connect(self._do_paste)
        add_row.addWidget(paste_btn)
        v.addLayout(add_row)

        self._add_err = QLabel("")
        self._add_err.setStyleSheet(f"color:{RED};font-size:11px;")
        v.addWidget(self._add_err)

        # Scroll list
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._list_widget = QWidget()
        self._list_widget.setStyleSheet("background:transparent;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(4)
        self._list_layout.addStretch()
        self._scroll.setWidget(self._list_widget)
        v.addWidget(self._scroll, stretch=1)

        self._replace_content(w)
        self._reload_items()

    def _reload_items(self) -> None:
        # Remove all item cards (keep only stretch at end)
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        try:
            items = self._vault.get_items()
        except RuntimeError:
            return

        if not items:
            placeholder = QLabel(i18n.get("vault.no_items"))
            placeholder.setStyleSheet(f"color:{TEXT_DIM};font-size:12px;padding:20px;")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._list_layout.insertWidget(0, placeholder)
            return

        for item in items:
            card = self._make_item_card(item)
            self._list_layout.insertWidget(self._list_layout.count() - 1, card)

    def _make_item_card(self, item: dict) -> QWidget:
        card = QWidget()
        card.setFixedHeight(52)
        card.setStyleSheet(
            f"background:{BG_CARD};border:1px solid {BORDER};border-radius:8px;"
        )
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 0, 10, 0)
        row.setSpacing(8)

        label_lbl = QLabel(item["label"] or i18n.get("vault.no_label"))
        label_lbl.setStyleSheet(f"color:{TEXT};font-size:12px;font-weight:600;")
        label_lbl.setFixedWidth(130)
        label_lbl.setWordWrap(False)
        row.addWidget(label_lbl)

        masked = QLabel("••••••••••••")
        masked.setStyleSheet(
            f"color:{TEXT_DIM};font-family:'Consolas',monospace;font-size:12px;"
        )
        masked.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(masked, stretch=1)

        # Toggle show/hide
        self._shown[item["id"]] = False
        show_btn = _btn(i18n.get("common.show"), BG_HOVER, TEXT_DIM, BORDER)

        def _toggle(_, iid=item["id"], plain=item["plaintext"],
                    mlbl=masked, sbtn=show_btn):
            self._shown[iid] = not self._shown[iid]
            if self._shown[iid]:
                mlbl.setText(plain)
                sbtn.setText(i18n.get("common.hide"))
            else:
                mlbl.setText("••••••••••••")
                sbtn.setText(i18n.get("common.show"))

        show_btn.clicked.connect(_toggle)
        row.addWidget(show_btn)

        copy_btn = _btn(i18n.get("common.copy"), ACCENT_DIM, TEXT, BORDER)
        copy_btn.clicked.connect(
            lambda _, t=item["plaintext"]: self._copy_item(t)
        )
        row.addWidget(copy_btn)

        del_btn = _btn(i18n.get("common.delete"), RED_DIM, "#FFB3B3", RED)
        del_btn.clicked.connect(lambda _, iid=item["id"]: self._do_delete(iid))
        row.addWidget(del_btn)

        return card

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _do_add(self) -> None:
        label   = self._new_label.text().strip()
        content = self._new_content.text()
        if not content:
            self._add_err.setText(i18n.get("vault.errors.secret_empty"))
            return
        try:
            self._vault.add_item(content, label)
            self._new_label.clear()
            self._new_content.clear()
            self._add_err.setText("")
            self._reload_items()
        except Exception as exc:
            self._add_err.setText(str(exc))

    def _do_paste(self) -> None:
        text = QApplication.clipboard().text()
        if text:
            self._new_content.setText(text)
        else:
            self._add_err.setText(i18n.get("vault.errors.clipboard_empty"))

    def _copy_item(self, text: str) -> None:
        QApplication.clipboard().setText(text)

    def _do_delete(self, vault_id: int) -> None:
        if confirm(
            self,
            i18n.get("vault.delete_item"),
            i18n.get("vault.delete_confirm"),
            confirm_key="common.yes",
            cancel_key="common.no",
            danger=True,
        ):
            self._vault.delete_item(vault_id)
            self._reload_items()

    def _do_lock(self) -> None:
        self._vault.lock()
        self._show_unlock_view()

    def _do_change_pin(self) -> None:
        old_pin, ok1 = prompt_text(
            self,
            i18n.get("vault.change_pin_action"),
            i18n.get("vault.current_pin"),
            password=True,
        )
        if not ok1 or not old_pin:
            return
        if not self._vault.verify_pin(old_pin):
            message(self, i18n.get("vault.change_pin_action"), i18n.get("vault.errors.current_pin_incorrect"))
            return
        new_pin, ok2 = prompt_text(
            self,
            i18n.get("vault.change_pin_action"),
            i18n.get("vault.new_pin"),
            password=True,
        )
        if not ok2 or not new_pin:
            return
        confirm_pin, ok3 = prompt_text(
            self,
            i18n.get("vault.change_pin_action"),
            i18n.get("vault.confirm_new_pin"),
            password=True,
        )
        if not ok3 or new_pin != confirm_pin:
            message(self, i18n.get("vault.change_pin_action"), i18n.get("vault.errors.pin_mismatch"))
            return
        self._vault.setup_pin(new_pin)
        message(self, i18n.get("vault.change_pin_action"), i18n.get("vault.pin_changed"))
