"""
utils/styles.py
───────────────
Shared colour palette and button-style helpers for VeilClip.

All UI files import colours and style functions from here so every
widget automatically shares the same look and there is no duplication.

Usage
─────
    from utils.styles import *          # colours + helper functions
    from utils.styles import btn_primary, ACCENT   # specific names
"""

# ── Palette ───────────────────────────────────────────────────────────────────

BG         = "#0F1117"
BG_CARD    = "#1A1D27"
BG_HOVER   = "#22263A"
BG_GROUP   = "#14161F"
ACCENT     = "#6C63FF"
ACCENT_DIM = "#3D3880"
TEXT       = "#E8E8F0"
TEXT_DIM   = "#7B7D8E"
TEXT_GROUP = "#55586E"
BORDER     = "#2A2D3E"
BORDER_PIN = "#6C63FF"
RED        = "#FF4C4C"
RED_DIM    = "#4A1515"
GOLD       = "#F5C542"
GREEN      = "#3DCC6E"
ORANGE     = "#FF9F40"

GOLD       = "#F5C542"
GREEN      = "#3DCC6E"
ORANGE     = "#FF9F40"

# Pinned card background (used in item_card.py)
BG_PINNED  = "#1E1B3A"


# ── Button style helpers ──────────────────────────────────────────────────────

def btn_primary() -> str:
    """Accent-coloured button with white text. Use for main actions."""
    return (
        f"QPushButton {{ background:{ACCENT}; color:white; border:none;"
        f" border-radius:7px; padding:4px 14px;"
        f" font-family:'Segoe UI',sans-serif; font-size:12px; font-weight:700; }}"
        f"QPushButton:hover {{ background:#7D75FF; }}"
        f"QPushButton:pressed {{ background:{ACCENT_DIM}; }}"
    )


def btn_ghost() -> str:
    """Transparent button with dim text and a thin border. Use for secondary actions."""
    return (
        f"QPushButton {{ background:transparent; color:{TEXT_DIM}; border:1px solid {BORDER};"
        f" border-radius:7px; padding:4px 14px;"
        f" font-family:'Segoe UI',sans-serif; font-size:12px; font-weight:600; }}"
        f"QPushButton:hover {{ background:{BG_HOVER}; color:{TEXT}; border-color:{ACCENT_DIM}; }}"
        f"QPushButton:pressed {{ background:{BG_CARD}; }}"
    )


def btn_danger() -> str:
    """Dark-red button that goes bright-red on hover. Use for destructive actions."""
    return (
        f"QPushButton {{ background:{RED_DIM}; color:#FFB3B3; border:1px solid {RED};"
        f" border-radius:7px; padding:4px 14px;"
        f" font-family:'Segoe UI',sans-serif; font-size:12px; font-weight:700; }}"
        f"QPushButton:hover {{ background:{RED}; color:white; }}"
        f"QPushButton:pressed {{ background:#CC3333; color:white; }}"
    )


def btn_icon(size: int = 26) -> str:
    """Square icon-only button (no border, transparent background)."""
    return (
        f"QPushButton {{ background:transparent; color:{TEXT_DIM}; border:none;"
        f" border-radius:6px; font-size:14px; min-width:{size}px; min-height:{size}px; }}"
        f"QPushButton:hover {{ background:{BG_HOVER}; color:{TEXT}; }}"
        f"QPushButton:pressed {{ background:{ACCENT}; color:white; }}"
    )


def scrollbar_style() -> str:
    """Shared thin scrollbar style."""
    return (
        f"QScrollArea {{ background:transparent; border:none; }}"
        f"QScrollBar:vertical {{ background:{BG_CARD}; width:5px; border-radius:3px; }}"
        f"QScrollBar::handle:vertical {{ background:{ACCENT_DIM}; border-radius:3px; min-height:24px; }}"
        f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}"
    )
