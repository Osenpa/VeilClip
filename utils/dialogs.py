from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import utils.i18n as i18n
from utils.config import ICON_APP
from utils.styles import ACCENT, BG, BG_CARD, BG_HOVER, BORDER, RED, RED_DIM, TEXT, TEXT_DIM


def _button_style(bg: str, border: str = "", fg: str = "white") -> str:
    border_css = f"border:1px solid {border};" if border else "border:none;"
    hover_bg = bg if bg != "transparent" else BG_HOVER
    hover_fg = "white" if bg != "transparent" else TEXT
    return (
        f"QPushButton{{background:{bg};color:{fg};{border_css}"
        f"border-radius:7px;padding:4px 14px;font-family:'Segoe UI',sans-serif;"
        f"font-size:12px;font-weight:600;}}"
        f"QPushButton:hover{{background:{hover_bg};color:{hover_fg};}}"
    )


def _apply_window_icon(window) -> None:
    try:
        icon_path = Path(ICON_APP)
        if icon_path.exists():
            window.setWindowIcon(QIcon(str(icon_path)))
    except Exception:
        pass


def message(parent, title: str, text: str, ok_key: str = "common.ok") -> None:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    _apply_window_icon(dlg)
    dlg.setMinimumWidth(360)
    dlg.setStyleSheet(
        f"QDialog{{background:{BG};font-family:'Segoe UI',sans-serif;}}"
        f"QLabel{{background:transparent;color:{TEXT};}}"
    )

    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(22, 18, 22, 18)
    layout.setSpacing(14)

    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color:{TEXT}; font-size:12px;")
    layout.addWidget(label)

    ok_button = QPushButton(i18n.get(ok_key))
    ok_button.setFixedHeight(32)
    ok_button.setCursor(Qt.CursorShape.PointingHandCursor)
    ok_button.setStyleSheet(_button_style(ACCENT))
    ok_button.clicked.connect(dlg.accept)
    layout.addWidget(ok_button)

    dlg.exec()


def confirm(
    parent,
    title: str,
    text: str,
    confirm_key: str = "common.yes",
    cancel_key: str = "common.no",
    danger: bool = False,
) -> bool:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    _apply_window_icon(dlg)
    dlg.setMinimumWidth(360)
    dlg.setStyleSheet(
        f"QDialog{{background:{BG};font-family:'Segoe UI',sans-serif;}}"
        f"QLabel{{background:transparent;color:{TEXT};}}"
    )

    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(22, 18, 22, 18)
    layout.setSpacing(14)

    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color:{TEXT}; font-size:12px;")
    layout.addWidget(label)

    row = QHBoxLayout()
    row.setSpacing(8)
    row.addStretch()

    cancel_button = QPushButton(i18n.get(cancel_key))
    cancel_button.setFixedHeight(32)
    cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
    cancel_button.setStyleSheet(_button_style("transparent", BORDER, TEXT_DIM))
    cancel_button.clicked.connect(dlg.reject)
    row.addWidget(cancel_button)

    confirm_style = _button_style(RED_DIM if danger else ACCENT, RED if danger else ACCENT)
    confirm_button = QPushButton(i18n.get(confirm_key))
    confirm_button.setFixedHeight(32)
    confirm_button.setCursor(Qt.CursorShape.PointingHandCursor)
    confirm_button.setStyleSheet(confirm_style)
    confirm_button.clicked.connect(dlg.accept)
    row.addWidget(confirm_button)

    layout.addLayout(row)
    return dlg.exec() == QDialog.DialogCode.Accepted


def prompt_text(
    parent,
    title: str,
    label_text: str,
    text: str = "",
    placeholder: str = "",
    password: bool = False,
    ok_key: str = "common.ok",
    cancel_key: str = "common.cancel",
) -> tuple[str, bool]:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    _apply_window_icon(dlg)
    dlg.setMinimumWidth(380)
    dlg.setStyleSheet(
        f"QDialog{{background:{BG};font-family:'Segoe UI',sans-serif;}}"
        f"QLabel{{background:transparent;color:{TEXT};}}"
        f"QLineEdit{{background:{BG_CARD};color:{TEXT};border:1px solid {BORDER};"
        f"border-radius:6px;padding:6px 10px;font-size:12px;}}"
    )

    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(22, 18, 22, 18)
    layout.setSpacing(12)

    label = QLabel(label_text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color:{TEXT}; font-size:12px;")
    layout.addWidget(label)

    field = QLineEdit()
    field.setText(text)
    field.setPlaceholderText(placeholder)
    if password:
        field.setEchoMode(QLineEdit.EchoMode.Password)
    layout.addWidget(field)

    row = QHBoxLayout()
    row.setSpacing(8)
    row.addStretch()

    cancel_button = QPushButton(i18n.get(cancel_key))
    cancel_button.setFixedHeight(32)
    cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
    cancel_button.setStyleSheet(_button_style("transparent", BORDER, TEXT_DIM))
    cancel_button.clicked.connect(dlg.reject)
    row.addWidget(cancel_button)

    ok_button = QPushButton(i18n.get(ok_key))
    ok_button.setFixedHeight(32)
    ok_button.setCursor(Qt.CursorShape.PointingHandCursor)
    ok_button.setStyleSheet(_button_style(ACCENT))
    ok_button.clicked.connect(dlg.accept)
    row.addWidget(ok_button)

    layout.addLayout(row)

    field.setFocus()
    accepted = dlg.exec() == QDialog.DialogCode.Accepted
    return field.text(), accepted


def prompt_int(
    parent,
    title: str,
    label_text: str,
    value: int,
    minimum: int,
    maximum: int,
    ok_key: str = "common.ok",
    cancel_key: str = "common.cancel",
) -> tuple[int, bool]:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    _apply_window_icon(dlg)
    dlg.setMinimumWidth(360)
    dlg.setStyleSheet(
        f"QDialog{{background:{BG};font-family:'Segoe UI',sans-serif;}}"
        f"QLabel{{background:transparent;color:{TEXT};}}"
        f"QSpinBox{{background:{BG_CARD};color:{TEXT};border:1px solid {BORDER};"
        f"border-radius:6px;padding:4px 8px;font-size:12px;}}"
    )

    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(22, 18, 22, 18)
    layout.setSpacing(12)

    label = QLabel(label_text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color:{TEXT}; font-size:12px;")
    layout.addWidget(label)

    spin = QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setValue(value)
    layout.addWidget(spin)

    row = QHBoxLayout()
    row.setSpacing(8)
    row.addStretch()

    cancel_button = QPushButton(i18n.get(cancel_key))
    cancel_button.setFixedHeight(32)
    cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
    cancel_button.setStyleSheet(_button_style("transparent", BORDER, TEXT_DIM))
    cancel_button.clicked.connect(dlg.reject)
    row.addWidget(cancel_button)

    ok_button = QPushButton(i18n.get(ok_key))
    ok_button.setFixedHeight(32)
    ok_button.setCursor(Qt.CursorShape.PointingHandCursor)
    ok_button.setStyleSheet(_button_style(ACCENT))
    ok_button.clicked.connect(dlg.accept)
    row.addWidget(ok_button)

    layout.addLayout(row)

    spin.setFocus()
    accepted = dlg.exec() == QDialog.DialogCode.Accepted
    return spin.value(), accepted
