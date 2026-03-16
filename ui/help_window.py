"""
ui/help_window.py
─────────────────
VeilClip Help & Support window.
Plain-language, child-friendly guide covering all 20 features.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore    import Qt, QUrl
from PyQt6.QtGui     import QDesktopServices, QIcon
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFrame, QHBoxLayout,
    QLabel, QScrollArea, QVBoxLayout, QWidget,
)

import utils.i18n as i18n
from utils.config import APP_NAME, ICON_APP
from utils.qt_i18n import translate_labels

logger = logging.getLogger(__name__)

BG       = "#0F1117"
BG_CARD  = "#1A1D27"
BG_HOVER = "#22263A"
ACCENT   = "#6C63FF"
TEXT     = "#E8E8F0"
TEXT_DIM = "#7B7D8E"
BORDER   = "#2A2D3E"

CONTACT_EMAIL   = "osenpacom@gmail.com"
CONTACT_WEBSITE = "https://osenpa.com/veilclip"

HELP_SECTIONS = [
    {
        "title": "1.  What is VeilClip?",
        "body": (
            "VeilClip is a clipboard manager for Windows. Think of it like a "
            "notebook that automatically writes down everything you copy — text, "
            "links, images, and file paths — so you can go back and use any of "
            "them again whenever you want.\n\n"
            "Normally, your computer only remembers the very last thing you "
            "copied. The moment you copy something new, the old thing disappears "
            "forever. VeilClip fixes that problem. It quietly sits in the "
            "background and saves every single thing you copy, so nothing is "
            "ever lost by accident.\n\n"
            "VeilClip is completely free to use and always will be. It is "
            "open-source, which means anyone can read the program code and "
            "check exactly what it does — there are no hidden surprises."
        ),
    },
    {
        "title": "2.  Your Privacy & Security — 100 % Offline",
        "body": (
            "This is the most important thing to know about VeilClip, so please "
            "read it carefully.\n\n"
            "VeilClip works 100 % offline. It never connects to the internet. "
            "It does not send your clipboard data to any server, any company, "
            "or any person. Everything you copy is saved only in a small "
            "database file that lives on your own computer.\n\n"
            "No cloud. No sync. No account required. No tracking. No "
            "advertisements. Nobody except you can ever see what you have copied.\n\n"
            "You can use VeilClip on a plane, in a cabin with no wifi, or "
            "completely disconnected from the internet — it will work exactly "
            "the same as always.\n\n"
            "VeilClip is open-source. The full code is publicly available for "
            "anyone to inspect. What you see is exactly what the program does — "
            "nothing is hidden.\n\n"
            "VeilClip is free to use. Updates and new features are made possible "
            "by people who choose to donate. If VeilClip saves you time, please "
            "consider supporting it — every contribution helps keep the project "
            "alive. See section 19 for more."
        ),
    },
    {
        "title": "3.  Starting VeilClip",
        "body": (
            "When VeilClip starts, it goes straight to the system tray — the "
            "small area near the clock in the bottom-right corner of your screen. "
            "You will see a small VeilClip icon there.\n\n"
            "VeilClip begins watching your clipboard immediately. Every time you "
            "press Ctrl+C to copy something, VeilClip saves it automatically. "
            "You do not need to do anything special — it just works quietly in "
            "the background.\n\n"
            "By default, VeilClip is set to start automatically every time you "
            "turn on your computer, so you never have to remember to open it. "
            "You can turn this off in Settings under Window Behaviour."
        ),
    },
    {
        "title": "4.  Opening and Closing the Clipboard Panel",
        "body": (
            "The clipboard panel is the main window where you can see everything "
            "you have copied.\n\n"
            "There are two ways to open it:\n\n"
            "Option 1 — Keyboard shortcut: Press Alt + V at the same time. "
            "This works from anywhere on your computer, even when you are inside "
            "another program. The panel will appear near your mouse cursor.\n\n"
            "Option 2 — Tray icon: Click the VeilClip icon in the system tray "
            "at the bottom-right corner of the screen near the clock.\n\n"
            "To close the panel:\n"
            "  •  Press the Escape key\n"
            "  •  Click the X button at the top-right of the panel\n"
            "  •  Press Alt+V again\n"
            "  •  Click anywhere outside the panel (if that option is turned on)\n\n"
            "The panel remembers its size and position between sessions. You can "
            "drag it anywhere on screen by holding the top bar, and resize it by "
            "dragging the bottom-right corner."
        ),
    },
    {
        "title": "5.  Using the Clipboard List",
        "body": (
            "When you open the panel, you will see a list of everything you have "
            "copied. The most recent item is always at the top.\n\n"
            "To copy an item again: Simply click on it. It is instantly copied "
            "to your clipboard and you can paste it anywhere with Ctrl+V.\n\n"
            "Each item shows a small icon that tells you what type it is:\n"
            "  📄  Text — a piece of written text\n"
            "  🔗  Link — a web address (URL)\n"
            "  🖼  Image — a picture\n"
            "  📁  File path — the location of a file on your computer\n\n"
            "Color preview: If you copy a colour code like #6C63FF or "
            "rgb(108, 99, 255), VeilClip shows a small coloured square next to "
            "the item so you can see the actual colour at a glance. Clicking "
            "the square copies just the colour code.\n\n"
            "The item count at the top-right shows how many items are in your "
            "history. When you switch to the Favorites tab it shows your "
            "favorites count instead."
        ),
    },
    {
        "title": "6.  Searching Your History",
        "body": (
            "If you have many copied items and want to find a specific one "
            "quickly, use the search box at the top of the panel.\n\n"
            "Just start typing — the list instantly filters to show only items "
            "that match what you typed. It searches both the content of the item "
            "and the name of the program it came from.\n\n"
            "To clear the search and see all items again: press Escape, or "
            "click the small X button inside the search box.\n\n"
            "Group mode: Click the Group button next to the search box to "
            "organise your history by the application each item came from. For "
            "example, all text copied from a browser will appear together, and "
            "all text from Notepad will appear in its own group."
        ),
    },
    {
        "title": "7.  Pinning Important Items",
        "body": (
            "If there is something you want to keep forever — like your home "
            "address, a piece of text you use very often, or a frequently used "
            "link — you can pin it so it is always at the top of your list.\n\n"
            "To pin an item: Right-click on it and choose Pin, or click the "
            "pin button (📌) on the right side of the item card.\n\n"
            "Pinned items always appear at the top of the list, above everything "
            "else. They are never automatically deleted, even if you have "
            "Auto-Delete History turned on. They also survive when you use "
            "Clear History.\n\n"
            "To unpin: right-click and choose Pin again, or click the pin "
            "button again. It works like a toggle."
        ),
    },
    {
        "title": "8.  Deleting Items and Undoing a Delete",
        "body": (
            "To delete a single item: Click the X button on the right side of "
            "the item card. The item disappears immediately from the list.\n\n"
            "Undo a delete: After deleting, a small notification appears at the "
            "top of the panel saying 'Deleted — Undo'. Click the Undo button "
            "or press Ctrl+Z on your keyboard to bring the item back. You have "
            "3 seconds to undo before the deletion becomes permanent.\n\n"
            "Multiple undo: If you delete several items one after another, you "
            "can undo them one by one — up to 8 consecutive deletions can be "
            "undone. The notification shows how many deletions are pending.\n\n"
            "When you close the panel, all pending deletions are committed "
            "immediately and can no longer be undone."
        ),
    },
    {
        "title": "9.  Selecting Multiple Items at Once",
        "body": (
            "You can select several items at the same time to copy or delete "
            "them all in one go — much faster than doing them one by one.\n\n"
            "To enter Select mode: Click the 'Select' button in the top-right "
            "area of the panel header.\n\n"
            "Once in Select mode, click on any item to select it. A count of "
            "selected items is shown at the top of the panel. Click a selected "
            "item again to deselect it.\n\n"
            "Copy all selected: Click 'Copy' in the toolbar to combine all "
            "selected text items into one and copy them to your clipboard. "
            "Images cannot be multi-copied this way.\n\n"
            "Delete all selected: Click 'Delete' to remove all selected items "
            "at once. You can undo this with Ctrl+Z.\n\n"
            "To leave Select mode: Click 'Cancel', or switch tabs."
        ),
    },
    {
        "title": "10.  Editing Text Items",
        "body": (
            "Sometimes you copy something but want to change it slightly before "
            "using it — for example removing extra spaces, fixing a typo, or "
            "adjusting part of a link.\n\n"
            "To edit a text item: Right-click on it and choose 'Edit Text'. A "
            "text editor will open where you can change the content however you "
            "like. When you click OK, the updated text is saved to your history "
            "and automatically copied to your clipboard.\n\n"
            "You can also copy an item as plain text: Right-click and choose "
            "'Copy as Plain Text'. This removes any rich formatting (bold, "
            "italic, special characters) and copies just the plain words. "
            "Useful when pasting into a program that does not accept formatted text."
        ),
    },
    {
        "title": "11.  The Image Editor",
        "body": (
            "VeilClip has a built-in image editor for any image in your "
            "clipboard history.\n\n"
            "To open it: Right-click on any image item and choose 'Edit Image'.\n\n"
            "Inside the image editor you can:\n"
            "  •  Crop — cut out just the part of the image you want\n"
            "  •  Rotate — turn the image left or right\n"
            "  •  Flip — mirror the image horizontally or vertically\n"
            "  •  Resize — change the dimensions of the image\n"
            "  •  Adjust brightness, contrast, and other settings\n\n"
            "When you save, the result is added to your clipboard history as a "
            "new image item, ready to copy and paste."
        ),
    },
    {
        "title": "12.  Favorites — Save What You Use Most",
        "body": (
            "Favorites is a special place where you can save items you want to "
            "keep permanently and find quickly, without scrolling through your "
            "whole history.\n\n"
            "To add an item to Favorites: Right-click on it and hover over "
            "'Add to Favorites'. Choose a category (Work, Personal, Passwords, "
            "General) or create a new category of your own.\n\n"
            "To view your Favorites: Click the 'Favorites' tab at the top of "
            "the panel.\n\n"
            "Search Favorites: Use the search bar at the top of the Favorites "
            "tab to filter saved items by text, app, or category.\n\n"
            "To copy a favorite again: Click its card, just like a normal "
            "clipboard-history item.\n\n"
            "To drag a favorite into another app: Click and hold the card, "
            "then drag it where you want to drop it.\n\n"
            "Right-click a favorite: Open the same quick actions you use in "
            "clipboard history, including copy, copy as plain text, edit text, "
            "and edit image where supported.\n\n"
            "Filter by category: Click a category button at the top of the "
            "Favorites tab to show only that category. Click 'All' to see "
            "everything.\n\n"
            "Images: When you save an image to Favorites, a small thumbnail "
            "preview is shown on the card.\n\n"
            "Manage categories: Click the 'Manage' button in the Favorites tab "
            "to rename or delete your custom categories.\n\n"
            "To remove a favorite: Click the X button on its card or use the "
            "right-click menu. VeilClip will ask for confirmation first."
        ),
    },
    {
        "title": "13.  Dragging Items into Other Programs",
        "body": (
            "You can drag items directly from VeilClip into other programs — "
            "no need to copy and paste.\n\n"
            "For example: drag a link directly into a browser address bar. "
            "Drag an image directly into a photo editor, a document, or a "
            "folder on your desktop. Drag a file path into a terminal window.\n\n"
            "To drag an item: Click and hold the left mouse button on any item "
            "card, then move your mouse to where you want to drop it, and "
            "release the button.\n\n"
            "A small thumbnail of the item follows your mouse while you drag "
            "so you can see exactly what you are moving."
        ),
    },
    {
        "title": "14.  Locked Notes — Your PIN-Protected Secret Space",
        "body": (
            "Locked Notes is a hidden space inside VeilClip where you can store "
            "sensitive information — passwords, secret codes, private notes, or "
            "anything you want to keep safe from other people.\n\n"
            "Locked Notes are protected by a PIN that only you know. Nobody "
            "can see the contents without the correct PIN — not even someone "
            "who has physical access to your computer.\n\n"
            "Items saved in Locked Notes never appear in the main clipboard "
            "list. They are stored separately and encrypted.\n\n"
            "To open Locked Notes: Go to Settings, click 'Locked Notes', then "
            "click 'Open Locked Notes'. The first time, you will set a PIN. "
            "Every time after that, you will need to enter your PIN.\n\n"
            "Important: If you forget your PIN, your locked notes cannot be "
            "recovered. There is no password reset. Please choose a PIN you "
            "will remember."
        ),
    },
    {
        "title": "15.  Settings — Full Overview",
        "body": (
            "Open Settings by clicking the ⚙ button in the panel header, or "
            "right-clicking the tray icon and choosing Settings.\n\n"
            "HOTKEY — Change the keyboard shortcut (default Alt+V). Click "
            "Change, press your new combination. Use 'Reset to Default' to "
            "go back to Alt+V.\n\n"
            "WINDOW BEHAVIOUR:\n"
            "  •  Always open at cursor — panel appears at mouse position\n"
            "  •  Close after copying — panel closes when you click an item\n"
            "  •  Always on top — panel stays in front of all other windows\n"
            "  •  Close on outside click — clicking outside closes the panel\n"
            "  •  Run at Windows startup — starts with your computer\n\n"
            "HISTORY — Auto-delete old items after a chosen number of hours. "
            "Pinned items are always kept.\n\n"
            "STORAGE — See the database file location. Open the folder, copy "
            "the path, or move the database to a different drive.\n\n"
            "BACKUP — Automatically back up your database on a schedule to "
            "any folder you choose (see section 16).\n\n"
            "EXPORT / IMPORT — Save history to a file or load it back "
            "(see section 16).\n\n"
            "LOCKED NOTES — Open the PIN-protected vault (see section 14).\n\n"
            "PRIVACY — Clear history, clear pinned items, or Reset Everything "
            "to wipe all data and start fresh (see section 17)."
        ),
    },
    {
        "title": "16.  Backup and Export — Keep Your Data Safe",
        "body": (
            "VeilClip gives you two ways to make sure your clipboard history "
            "is never lost.\n\n"
            "AUTOMATIC BACKUP\n"
            "Go to Settings → Backup. Choose a folder on your computer or an "
            "external drive. Set how often to back up (e.g. every 24 hours) "
            "and how many copies to keep (e.g. the last 7). VeilClip will "
            "then back up automatically without any action from you. "
            "Click 'Back Up Now' to create a backup immediately at any time.\n\n"
            "EXPORT TO FILE\n"
            "Go to Settings → Export. Choose JSON (best for importing back "
            "into VeilClip) or CSV (opens in Excel or Google Sheets). "
            "A copy of your full clipboard history is saved to the file you "
            "choose.\n\n"
            "IMPORT FROM FILE\n"
            "Load a previously exported file back into VeilClip. The items are "
            "merged into your current history and any duplicates are skipped "
            "automatically."
        ),
    },
    {
        "title": "17.  Reset Everything — Starting Completely Fresh",
        "body": (
            "If you want to completely wipe VeilClip and start from scratch — "
            "as if you had just installed it for the first time — use Reset "
            "Everything.\n\n"
            "To use it: Go to Settings → Privacy → Reset Everything. A "
            "confirmation window will appear. Click 'Yes, Reset Everything'.\n\n"
            "What gets deleted:\n"
            "  •  All clipboard history (including pinned items)\n"
            "  •  All favorites\n"
            "  •  All locked notes\n"
            "  •  All settings and preferences\n"
            "  •  All temporary files\n\n"
            "After the reset, VeilClip restarts automatically and opens exactly "
            "as it does on a brand new installation — the welcome message "
            "appears and the panel opens.\n\n"
            "Warning: This cannot be undone. Export or back up anything "
            "important before using this option."
        ),
    },
    {
        "title": "18.  The Tray Icon and Its Menu",
        "body": (
            "The VeilClip icon lives in the system tray at the bottom-right "
            "corner of your screen, near the clock.\n\n"
            "Left-click or double-click the icon to open the clipboard panel.\n\n"
            "Right-click the icon for a quick menu:\n"
            "  Open — opens the clipboard panel\n"
            "  Settings — opens the Settings window\n"
            "  Clear History — deletes all non-pinned items\n"
            "  Donate — opens the donation window\n"
            "  Help — opens this help window\n"
            "  Exit — closes VeilClip completely\n\n"
            "When you choose Exit, your history is saved and will still be "
            "there the next time you start VeilClip."
        ),
    },
    {
        "title": "19.  Free Forever — Kept Alive by Your Support",
        "body": (
            "VeilClip is completely free to use and will always remain free. "
            "There is no paid version, no subscription, and no features locked "
            "behind a paywall.\n\n"
            "VeilClip is developed and maintained by independent developers who "
            "work on it in their spare time. There are no big company budgets — "
            "just real people building something genuinely useful for everyone.\n\n"
            "New features, bug fixes, and updates for future versions of Windows "
            "are made possible entirely by donations from users like you. When "
            "you donate, you are directly funding the next improvement to VeilClip.\n\n"
            "How to donate:\n"
            "  •  Click the 💜 button in the panel header\n"
            "  •  Right-click the tray icon and choose Donate\n"
            "  •  Buy Me a Coffee (card / PayPal) or cryptocurrency (Bitcoin, "
            "Ethereum, USDT, Solana, and many more)\n\n"
            "Even the smallest donation makes a real difference and is deeply "
            "appreciated. If VeilClip saves you time every day, please consider "
            "giving something back — it helps keep this project alive and "
            "growing for everyone.\n\n"
            "Thank you for using VeilClip."
        ),
    },
    {
        "title": "20.  Quick Tips & Keyboard Shortcuts",
        "body": (
            "The most useful shortcuts and tips:\n\n"
            "Alt+V — open or close the panel from anywhere\n"
            "Escape — close the panel (or clear the search if text is typed)\n"
            "Ctrl+Z — undo the last item deletion (within 3 seconds)\n"
            "Click an item — copy it to clipboard instantly\n"
            "Right-click an item — edit, pin, add to favorites, delete\n"
            "Drag an item — drop it directly into another program\n\n"
            "Tip: Use 'Select' mode to delete many old items at once — much "
            "faster than one by one.\n\n"
            "Tip: Save things you type often (your email address, a code "
            "snippet, a standard reply) to Favorites for instant one-click "
            "access. Favorites can also be clicked to copy or dragged into "
            "other apps later. Use the Favorites search bar and right-click "
            "menu to manage them faster, no matter how long your history "
            "gets.\n\n"
            "Tip: Store passwords and private codes in Locked Notes — they "
            "never appear in the main clipboard list and are always "
            "PIN-protected.\n\n"
            "Tip: Set up automatic backups to an external drive so your history "
            "is safe even if something happens to your computer.\n\n"
            "Tip: You can resize the panel by dragging its bottom-right corner. "
            "The size and position are remembered next time you open it."
        ),
    },
]


def _sep() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"color:{BORDER}; background:{BORDER}; border:none;")
    line.setFixedHeight(1)
    return line


class _ClickableLabel(QLabel):
    def __init__(self, text: str, on_click, tooltip: str = "", parent=None):
        super().__init__(text, parent)
        self._on_click = on_click
        self._base  = (
            f"color:{ACCENT}; font-family:'Consolas',monospace; font-size:12px; "
            f"background:{BG}; border:1px solid {BORDER}; border-radius:6px; padding:5px 10px;"
        )
        self._hover = (
            f"color:{ACCENT}; font-family:'Consolas',monospace; font-size:12px; "
            f"background:{BG_HOVER}; border:1px solid {ACCENT}66; border-radius:6px; padding:5px 10px;"
        )
        self.setStyleSheet(self._base)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)

    def enterEvent(self, e):
        self.setStyleSheet(self._hover); super().enterEvent(e)

    def leaveEvent(self, e):
        self.setStyleSheet(self._base); super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._on_click()
        super().mousePressEvent(e)


class HelpWindow(QDialog):
    """Help & Support window for VeilClip."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(i18n.literal("Help & Support"))
        icon_path = Path(ICON_APP)
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setMinimumSize(660, 700)
        self.setMaximumSize(900, 1000)
        self.resize(740, 840)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowMaximizeButtonHint)
        self.setStyleSheet(f"""
            QDialog, QWidget {{ background:{BG}; color:{TEXT}; font-family:'Segoe UI',sans-serif; }}
            QLabel {{ background:transparent; border:none; }}
            QScrollArea {{ background:transparent; border:none; }}
            QScrollBar:vertical {{ background:{BG_CARD}; width:5px; border-radius:3px; }}
            QScrollBar::handle:vertical {{ background:#3D3880; border-radius:3px; min-height:24px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        """)
        self._build_ui()
        translate_labels(self)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        il = QVBoxLayout(inner)
        il.setContentsMargins(0, 0, 10, 10)
        il.setSpacing(10)

        il.addWidget(self._make_header())

        sections = i18n.data("help.sections", HELP_SECTIONS)
        for section in sections:
            il.addWidget(self._make_section(section))

        il.addWidget(_sep())
        il.addWidget(self._make_contact())
        il.addStretch()

        scroll.setWidget(inner)
        root.addWidget(scroll)

    def _make_header(self) -> QWidget:
        card = QWidget()
        card.setStyleSheet(f"background:{BG_CARD}; border:none; border-radius:12px;")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(8)

        t1 = QLabel("Help & Support")
        t1.setStyleSheet(f"color:{TEXT}; font-size:16px; font-weight:700;")

        t2 = QLabel(
            "A complete guide to VeilClip — 20 sections covering every feature. "
            "Read any section you need, or start from the beginning."
        )
        t2.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
        t2.setWordWrap(True)

        badge_row = QWidget()
        badge_row.setStyleSheet("background:transparent;")
        br = QHBoxLayout(badge_row)
        br.setContentsMargins(0, 2, 0, 0)
        br.setSpacing(8)

        for label, color in (
            ("100 % Offline", "#3DCC6E"),
            ("Local Storage Only", "#6C63FF"),
            ("Open-Source", "#F7931A"),
            ("Free Forever", "#26A17B"),
        ):
            b = QLabel(label)
            b.setStyleSheet(
                f"color:white; background:{color}; border-radius:10px;"
                f" font-size:9px; font-weight:700; padding:2px 8px;"
            )
            br.addWidget(b)
        br.addStretch()

        lay.addWidget(t1)
        lay.addWidget(t2)
        lay.addWidget(badge_row)
        return card

    def _make_section(self, section: dict) -> QWidget:
        card = QWidget()
        card.setStyleSheet(f"background:{BG_CARD}; border:none; border-radius:12px;")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(8)

        title = QLabel(section["title"])
        title.setStyleSheet(f"color:{TEXT}; font-size:13px; font-weight:700;")
        lay.addWidget(title)
        lay.addWidget(_sep())

        body = QLabel(section["body"])
        body.setStyleSheet(f"color:{TEXT_DIM}; font-size:11.5px;")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(body)
        return card

    def _make_contact(self) -> QWidget:
        card = QWidget()
        card.setStyleSheet(f"background:{BG_CARD}; border:none; border-radius:12px;")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)

        title = QLabel("Get in Touch")
        title.setStyleSheet(f"color:{TEXT}; font-size:13px; font-weight:700;")
        lay.addWidget(title)
        lay.addWidget(_sep())

        desc = QLabel(
            "If you have a question, found a bug, or just want to say hello, "
            "reach out through the channels below. Every message is read."
        )
        desc.setStyleSheet(f"color:{TEXT_DIM}; font-size:11.5px;")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        er = QHBoxLayout(); er.setSpacing(8)
        et = QLabel("Email")
        et.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px; font-weight:600; min-width:52px;")
        er.addWidget(et)
        el = _ClickableLabel(CONTACT_EMAIL, on_click=None, tooltip="Click to copy")
        def _copy():
            QApplication.clipboard().setText(CONTACT_EMAIL)
            el.setToolTip("Copied!")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1600, lambda: el.setToolTip("Click to copy"))
        el._on_click = _copy
        er.addWidget(el, stretch=1)
        lay.addLayout(er)

        wr = QHBoxLayout(); wr.setSpacing(8)
        wt = QLabel("Website")
        wt.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px; font-weight:600; min-width:52px;")
        wr.addWidget(wt)
        wl = _ClickableLabel(
            CONTACT_WEBSITE.replace("https://", ""),
            on_click=lambda: QDesktopServices.openUrl(QUrl(CONTACT_WEBSITE)),
            tooltip="Click to open in browser",
        )
        wr.addWidget(wl, stretch=1)
        lay.addLayout(wr)
        return card
