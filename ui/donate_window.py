"""
ui/donate_window.py
───────────────────
VeilClip Donation window.

Shows Buy Me a Coffee link and all crypto wallet addresses with
embedded QR codes, styled to match the VeilClip dark theme.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore    import Qt
from PyQt6.QtGui     import QClipboard, QColor, QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QDialog, QGridLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget,
)

import utils.i18n as i18n
from utils.config import APP_NAME, ASSETS_DIR, ICON_APP
from utils.qt_i18n import translate_labels
from utils.styles import (
    BG, BG_CARD, BG_HOVER,
    ACCENT, TEXT, TEXT_DIM, BORDER,
    RED, GOLD, GREEN, ORANGE,
)

logger = logging.getLogger(__name__)

# ── Donation data ─────────────────────────────────────────────────────────────
BUYMEACOFFEE_URL = "https://buymeacoffee.com/osenpa"

CRYPTO_ENTRIES = [
    {
        "name":    "Bitcoin (BTC/SegWit)",
        "symbol":  "BTC",
        "color":   "#F7931A",
        "icon":    "₿",
        "address": "bc1q4v6c6a0ru4nf70p66rgwp92w3z89cpvh7a445e",
        "qr_key":  "bitcoin_btc_qr",
        "note":    None,
    },
    {
        "name":    "Ethereum (ERC-20)",
        "symbol":  "ETH",
        "color":   "#627EEA",
        "icon":    "Ξ",
        "address": "0xda8de84d6e71d180705d036eaa364b5324ee6b6d",
        "qr_key":  "ethereum_qr",
        "note":    None,
    },
    {
        "name":    "USDT (Tron / TRC-20)",
        "symbol":  "USDT",
        "color":   "#26A17B",
        "icon":    "₮",
        "address": "TEvxij9k6jKjkj19VSS62KYR9VKF8YodJg",
        "qr_key":  "usdt_trc20_qr",
        "note":    None,
    },
    {
        "name":    "USDT (Ethereum / ERC-20)",
        "symbol":  "USDT",
        "color":   "#26A17B",
        "icon":    "₮",
        "address": "0xda8de84d6e71d180705d036eaa364b5324ee6b6d",
        "qr_key":  "usdt_erc20_qr",
        "note":    None,
    },
    {
        "name":    "USDC (Ethereum / ERC-20)",
        "symbol":  "USDC",
        "color":   "#2775CA",
        "icon":    "$",
        "address": "0xda8de84d6e71d180705d036eaa364b5324ee6b6d",
        "qr_key":  "usdc_erc20_qr",
        "note":    None,
    },
    {
        "name":    "USDC (Solana)",
        "symbol":  "USDC",
        "color":   "#2775CA",
        "icon":    "$",
        "address": "66EyabUsviRTsGZnr3xZtw2XMQ1Eyd5cEK43VqT1R4He",
        "qr_key":  "usdc_solana_qr",
        "note":    None,
    },
    {
        "name":    "BNB (BEP-20)",
        "symbol":  "BNB",
        "color":   "#F3BA2F",
        "icon":    "◈",
        "address": "0xda8de84d6e71d180705d036eaa364b5324ee6b6d",
        "qr_key":  "bnb_bep20_qr",
        "note":    None,
    },
    {
        "name":    "Solana (SOL)",
        "symbol":  "SOL",
        "color":   "#9945FF",
        "icon":    "◎",
        "address": "66EyabUsviRTsGZnr3xZtw2XMQ1Eyd5cEK43VqT1R4He",
        "qr_key":  "solana_qr",
        "note":    None,
    },
    {
        "name":    "Dash",
        "symbol":  "DASH",
        "color":   "#008CE7",
        "icon":    "D",
        "address": "Xjw4Jg2rjXcYnaWvTGaBJWvDLR289yqhzR",
        "qr_key":  "dash_qr",
        "note":    None,
    },
    {
        "name":    "Litecoin (LTC)",
        "symbol":  "LTC",
        "color":   "#BFBBBB",
        "icon":    "Ł",
        "address": "LPECpKGpcMk9f4dLnxC1JYSvGVyv5m7GNg",
        "qr_key":  "litecoin_qr",
        "note":    None,
    },
    {
        "name":    "Cardano (ADA)",
        "symbol":  "ADA",
        "color":   "#0033AD",
        "icon":    "₳",
        "address": "addr1vyeaxft88ztd4yw39r3c9s623tdq23k3pg05v3aznhn7xds9pfw7x",
        "qr_key":  "cardano_qr",
        "note":    None,
    },
    {
        "name":    "Dogecoin (DOGE)",
        "symbol":  "DOGE",
        "color":   "#C2A633",
        "icon":    "Ð",
        "address": "DQj2XmPutvqEWPA7fErsyAsejHYyiGxEX4",
        "qr_key":  "doge_qr",
        "note":    None,
    },
    {
        "name":    "Bitcoin Cash (BCH)",
        "symbol":  "BCH",
        "color":   "#8DC351",
        "icon":    "Ƀ",
        "address": "14URHQqheuRis7HBUrrvw5dPh7bLeTM2zL",
        "qr_key":  "bitcoin_cash_qr",
        "note":    "⚠  BCH only — do NOT send regular Bitcoin (BTC) to this address.",
    },
]


# ── QR loader ─────────────────────────────────────────────────────────────────

_DONATE_ASSETS = ASSETS_DIR / "donate"


def _load_qr(key: str) -> QPixmap | None:
    try:
        png_path = _DONATE_ASSETS / f"{key}.png"
        if not png_path.exists():
            return None
        pm = QPixmap(str(png_path))
        return pm if not pm.isNull() else None
    except Exception as exc:
        logger.debug("QR load failed for %s: %s", key, exc)
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _card() -> QWidget:
    w = QWidget()
    w.setObjectName("donateCard")
    w.setStyleSheet(
        f"QWidget#donateCard {{ background:{BG_CARD}; border:none; border-radius:12px; }}"
    )
    return w


def _sep() -> QWidget:
    line = QWidget()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background:{BORDER}; border:none;")
    return line


def _copy_btn(text: str) -> QPushButton:
    b = QPushButton("Copy")
    b.setFixedHeight(28)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(f"""
        QPushButton {{
            background: transparent;
            color: {TEXT_DIM};
            border: 1px solid {BORDER};
            border-radius: 6px;
            font-family: 'Segoe UI', sans-serif;
            font-size: 10px;
            font-weight: 600;
            padding: 0 10px;
        }}
        QPushButton:hover {{ background:{BG_HOVER}; color:{TEXT}; border-color:{ACCENT}; }}
        QPushButton:pressed {{ background:{ACCENT}; color:white; border-color:{ACCENT}; }}
    """)
    _addr = text  # capture

    def _do_copy():
        QApplication.clipboard().setText(_addr)
        b.setText("✓ Copied")
        b.setStyleSheet(b.styleSheet().replace(f"color: {TEXT_DIM}", f"color: {GREEN}"))
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1800, lambda: (
            b.setText("Copy"),
            b.setStyleSheet(b.styleSheet().replace(f"color: {GREEN}", f"color: {TEXT_DIM}"))
        ))

    b.clicked.connect(_do_copy)
    return b


# ── DonateWindow ──────────────────────────────────────────────────────────────

class DonateWindow(QDialog):
    """Donation window showing Buy Me a Coffee + all crypto addresses."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(i18n.literal("Support the Developer"))
        icon_path = Path(ICON_APP)
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setMinimumSize(660, 700)
        self.setMaximumSize(800, 900)
        self.resize(720, 780)
        # Disable maximize button to prevent accidental full-screen
        self.setWindowFlags(
            self.windowFlags()
            & ~Qt.WindowType.WindowMaximizeButtonHint
        )
        self.setStyleSheet(f"""
            QDialog {{
                background: {BG};
                color: {TEXT};
                font-family: 'Segoe UI', sans-serif;
            }}
            QLabel {{ background: transparent; color: {TEXT}; }}
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{
                background: {BG_CARD}; width: 5px; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: #3D3880; border-radius: 3px; min-height: 24px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QTabWidget#donatetabs::pane {{
                border: none;
                background: transparent;
            }}
            QTabWidget#donateabs QTabBar::scroller {{ width: 0; }}
            QTabBar#donatebar::tab {{
                background: transparent;
                color: {TEXT_DIM};
                border: none;
                border-bottom: 2px solid transparent;
                padding: 8px 18px;
                font-size: 12px;
                font-weight: 600;
                margin-right: 2px;
            }}
            QTabBar#donatebar::tab:selected {{
                color: {TEXT};
                border-bottom: 2px solid {ACCENT};
            }}
            QTabBar#donatebar::tab:hover {{
                color: {TEXT};
            }}
        """)
        self._build_ui()
        translate_labels(self)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        # ── Top card: header + custom tab buttons, all inside one rounded card ─
        top_card = QWidget()
        top_card.setObjectName("donateTopCard")
        top_card.setStyleSheet(
            f"QWidget#donateTopCard {{ background:{BG_CARD}; border-radius:12px; border:none; }}"
        )
        top_v = QVBoxLayout(top_card)
        top_v.setContentsMargins(0, 0, 0, 0)
        top_v.setSpacing(0)

        # Header row
        header_row = QWidget()
        header_row.setStyleSheet("background:transparent;")
        h_lay = QHBoxLayout(header_row)
        h_lay.setContentsMargins(20, 16, 20, 12)
        h_lay.setSpacing(16)

        heart = QLabel("💜")
        heart.setStyleSheet("font-size:36px; background:transparent;")
        h_lay.addWidget(heart)

        txt_v = QVBoxLayout()
        txt_v.setSpacing(4)
        t1 = QLabel("Support VeilClip")
        t1.setStyleSheet(f"color:{TEXT}; font-size:16px; font-weight:700; background:transparent;")
        t2 = QLabel(
            "VeilClip is free and open-source. If you find it useful,\n"
            "consider buying the developer a coffee or donating crypto. 🙏"
        )
        t2.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px; background:transparent;")
        t2.setWordWrap(True)
        txt_v.addWidget(t1)
        txt_v.addWidget(t2)
        h_lay.addLayout(txt_v, stretch=1)
        top_v.addWidget(header_row)

        # Thin separator
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{BORDER}; border:none;")
        top_v.addWidget(sep)

        # Custom tab buttons row — lives inside the card, no gap possible
        tab_btn_row = QWidget()
        tab_btn_row.setStyleSheet("background:transparent;")
        tb_lay = QHBoxLayout(tab_btn_row)
        tb_lay.setContentsMargins(12, 4, 12, 0)
        tb_lay.setSpacing(4)

        active_tab_style = (
            f"QPushButton {{ background:transparent; color:{TEXT}; border:none;"
            f" border-bottom:2px solid {ACCENT}; border-radius:0;"
            f" font-size:12px; font-weight:700; padding:8px 16px; }}"
        )
        inactive_tab_style = (
            f"QPushButton {{ background:transparent; color:{TEXT_DIM}; border:none;"
            f" border-bottom:2px solid transparent; border-radius:0;"
            f" font-size:12px; font-weight:600; padding:8px 16px; }}"
            f"QPushButton:hover {{ color:{TEXT}; }}"
        )

        self._tab_bmc_btn  = QPushButton("Buy Me a Coffee")
        self._tab_cry_btn  = QPushButton("Crypto")
        for b in (self._tab_bmc_btn, self._tab_cry_btn):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedHeight(38)

        self._tab_bmc_btn.setStyleSheet(active_tab_style)
        self._tab_cry_btn.setStyleSheet(inactive_tab_style)

        tb_lay.addWidget(self._tab_bmc_btn)
        tb_lay.addWidget(self._tab_cry_btn)
        tb_lay.addStretch()
        top_v.addWidget(tab_btn_row)

        root.addWidget(top_card)

        # ── Tab content pages (no QTabWidget — just a stacked widget) ─────────
        from PyQt6.QtWidgets import QStackedWidget
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background:transparent;")
        self._stack.addWidget(self._make_bmc_tab())    # index 0
        self._stack.addWidget(self._make_crypto_tab()) # index 1
        self._stack.setCurrentIndex(0)
        root.addWidget(self._stack, stretch=1)

        # Wire tab buttons to stack
        def _switch(idx: int) -> None:
            self._stack.setCurrentIndex(idx)
            self._tab_bmc_btn.setStyleSheet(active_tab_style if idx == 0 else inactive_tab_style)
            self._tab_cry_btn.setStyleSheet(active_tab_style if idx == 1 else inactive_tab_style)

        self._tab_bmc_btn.clicked.connect(lambda: _switch(0))
        self._tab_cry_btn.clicked.connect(lambda: _switch(1))



    # ── Buy Me a Coffee tab ───────────────────────────────────────────────────

    def _make_bmc_tab(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(16)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        card = _card()
        cl   = QVBoxLayout(card)
        cl.setContentsMargins(24, 20, 24, 20)
        cl.setSpacing(14)

        # Icon + title
        top = QHBoxLayout()
        info = QVBoxLayout()
        info.setSpacing(3)
        t1 = QLabel("Buy Me a Coffee")
        t1.setStyleSheet(f"color:{TEXT}; font-size:15px; font-weight:700; background:transparent;")
        t2 = QLabel("The quickest way to show appreciation!")
        t2.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px; background:transparent;")
        info.addWidget(t1)
        info.addWidget(t2)
        top.addLayout(info, stretch=1)
        cl.addLayout(top)

        # QR code
        qr_pm = _load_qr("buymeacoffee_qr")
        if qr_pm:
            qr_row = QHBoxLayout()
            qr_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
            qr_lbl = QLabel()
            qr_lbl.setPixmap(qr_pm.scaled(
                160, 160,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
            qr_lbl.setStyleSheet(
                f"border:2px solid {BORDER}; border-radius:10px; "
                "background:white; padding:6px;"
            )
            qr_row.addWidget(qr_lbl)
            cl.addLayout(qr_row)

        # URL label — click to open in browser
        url_lbl = QLabel(BUYMEACOFFEE_URL)
        url_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        url_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        url_lbl.setToolTip("Click to open in browser")
        url_lbl.setStyleSheet(
            f"color:{ACCENT}; font-family:'Consolas',monospace; font-size:12px; "
            f"background:{BG}; border:1px solid {BORDER}; border-radius:6px; padding:6px 12px;"
        )
        url_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

        def _url_click(event):
            if event.button() == Qt.MouseButton.LeftButton:
                __import__('webbrowser').open(BUYMEACOFFEE_URL)
        url_lbl.mousePressEvent = _url_click
        cl.addWidget(url_lbl)

        lay.addWidget(card)
        lay.addStretch()
        return w

    # ── Crypto tab ────────────────────────────────────────────────────────────

    def _make_crypto_tab(self) -> QWidget:
        outer = QWidget()
        ol    = QVBoxLayout(outer)
        ol.setContentsMargins(0, 8, 0, 0)
        ol.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        il    = QVBoxLayout(inner)
        il.setContentsMargins(0, 0, 8, 8)
        il.setSpacing(10)

        for entry in CRYPTO_ENTRIES:
            il.addWidget(self._make_crypto_card(entry))

        il.addStretch()
        scroll.setWidget(inner)
        ol.addWidget(scroll)
        return outer

    def _make_crypto_card(self, entry: dict) -> QWidget:
        card  = _card()
        color = entry["color"]
        lay   = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        # ── Title row ─────────────────────────────────────────────────────────
        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        name_lbl = QLabel(entry["name"])
        name_lbl.setStyleSheet(f"color:{TEXT}; font-size:13px; font-weight:700; background:transparent;")
        title_row.addWidget(name_lbl, stretch=1)

        lay.addLayout(title_row)

        # ── Address + QR ──────────────────────────────────────────────────────
        content_row = QHBoxLayout()
        content_row.setSpacing(12)
        content_row.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Address section
        addr_col = QVBoxLayout()
        addr_col.setSpacing(6)

        # Clickable address label — click anywhere on it to copy
        addr_lbl = QLabel(entry["address"])
        addr_lbl.setToolTip("Click to copy address")
        addr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        addr_lbl.setStyleSheet(
            f"color:{ACCENT}; font-family:'Consolas',monospace; font-size:10px; "
            f"background:{BG}; border:1px solid {BORDER}; border-radius:6px; "
            f"padding:6px 8px;"
        )
        addr_lbl.setWordWrap(True)
        addr_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        addr_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        _address = entry["address"]

        def _make_click_handler(lbl: QLabel, addr: str):
            def _on_click(event):
                if event.button() == Qt.MouseButton.LeftButton:
                    QApplication.clipboard().setText(addr)
                    orig = lbl.styleSheet()
                    lbl.setText("✓  Copied!")
                    lbl.setStyleSheet(orig.replace(f"color:{ACCENT}", f"color:{GREEN}"))
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(1500, lambda: (
                        lbl.setText(addr),
                        lbl.setStyleSheet(orig),
                    ))
            lbl.mousePressEvent = _on_click

        _make_click_handler(addr_lbl, _address)
        addr_col.addWidget(addr_lbl)
        addr_col.addWidget(_copy_btn(entry["address"]))

        if entry.get("note"):
            note = QLabel(entry["note"])
            note.setWordWrap(True)
            note.setStyleSheet(
                f"color:#FFB347; background:#2A1F00; border:1px solid #AA6600; "
                f"border-radius:6px; font-size:10px; padding:5px 8px;"
            )
            addr_col.addWidget(note)

        addr_col.addStretch()
        content_row.addLayout(addr_col, stretch=1)

        # QR code
        qr_pm = _load_qr(entry["qr_key"])
        if qr_pm:
            qr_lbl = QLabel()
            qr_lbl.setPixmap(qr_pm.scaled(
                100, 100,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
            qr_lbl.setFixedSize(108, 108)
            qr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            qr_lbl.setStyleSheet(
                "background:white; border-radius:8px; padding:4px;"
            )
            content_row.addWidget(qr_lbl, alignment=Qt.AlignmentFlag.AlignTop)

        lay.addLayout(content_row)
        return card


# ── Quick test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import utils.i18n as i18n
    logging.basicConfig(level=logging.DEBUG)
    from utils.config import LOCALE_DIR

    i18n.init(LOCALE_DIR)
    app = QApplication(sys.argv)
    win = DonateWindow()
    win.show()
    sys.exit(app.exec())
