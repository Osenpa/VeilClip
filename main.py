"""
VeilClip — The Stealth & Offline Clipboard for Windows
Entry Point — Run from the VeilClip root folder:  python main.py
"""

import logging
import sys

from utils.config import ensure_dirs

ensure_dirs()

# Console: INFO and above (no noise in production)
# File:    DEBUG and above (rotated, for troubleshooting)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

# Rotating file handler — written after app dirs are created
def _setup_file_logging() -> None:
    try:
        from logging.handlers import RotatingFileHandler
        from utils.config import LOG_FILE, LOG_DIR, LOG_MAX_BYTES, LOG_BACKUP_COUNT
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            str(LOG_FILE), maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
            datefmt="%H:%M:%S"
        ))
        logging.getLogger().addHandler(fh)
    except Exception as _e:
        logging.warning("File logging unavailable: %s", _e)

_setup_file_logging()
logger = logging.getLogger("main")

from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon
from PyQt6.QtCore    import QTimer, Qt

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
app.setApplicationName("VeilClip")
app.setApplicationDisplayName("VeilClip")
app.setApplicationVersion("1.0.0")
app.setOrganizationName("Osenpa")
app.setOrganizationDomain("osenpa.com")
app.setStyleSheet("""
    QToolTip {
        background-color: #1A1D27;
        color: #E8E8F0;
        border: 1px solid #6C63FF;
        border-radius: 6px;
        font-family: 'Segoe UI', sans-serif;
        font-size: 11px;
        padding: 4px 8px;
    }
""")

import utils.i18n as i18n
from utils.qt_i18n          import install as install_qt_i18n
from utils.config           import APP_NAME, APP_TITLE, DB_PATH, DEFAULT_HOTKEY, AUTO_DELETE_HOURS, AUTO_DELETE_ENABLED, LOCALE_DIR, get_db_path
from utils.config_manager   import cfg as _cfg
from utils.hotkey           import HotkeyManager
from core.database          import Database
from core.clipboard_monitor import ClipboardMonitor
from core.backup            import BackupManager
from core.vault             import VaultManager
from ui.tray                import VeilClipTray
from ui.main_window         import VeilClipWindow

# i18n
i18n.init(
    locale_dir=LOCALE_DIR,
    language=_cfg.get("language"),
)
install_qt_i18n()
app.setLayoutDirection(
    Qt.LayoutDirection.RightToLeft if i18n.is_rtl() else Qt.LayoutDirection.LeftToRight
)
logger.info("Locale: %s", i18n.current_language())

if not QSystemTrayIcon.isSystemTrayAvailable():
    QMessageBox.critical(None, APP_NAME, i18n.get("errors.system_tray_unavailable"))
    sys.exit(1)

# DB
_active_db_path = get_db_path()
db = Database(db_path=_active_db_path)
db.init_db()
logger.info("DB ready: %s", _active_db_path)

# Backup manager
backup_manager = BackupManager(db_path=_active_db_path)
backup_manager.start()
logger.info("Backup manager started.")

# Vault manager
vault = VaultManager(db)

# Main window
main_window = VeilClipWindow(db=db, on_open_settings=lambda: open_settings(), on_open_donate=lambda: open_donate(), on_open_help=lambda: open_help())

# Settings window (lazy — imported on first use)
_settings_window = None

def _apply_always_on_top(enabled: bool) -> None:
    """Apply or remove WindowStaysOnTopHint to ALL VeilClip windows."""
    try:
        _cfg.set("always_on_top", enabled)
    except Exception:
        pass
    # Clipboard panel
    main_window.set_always_on_top(enabled)
    # Secondary windows (only if already created)
    hint = Qt.WindowType.WindowStaysOnTopHint
    for win in [_settings_window, _donate_window, _help_window]:
        if win is None:
            continue
        flags = win.windowFlags()
        if enabled:
            flags |= hint
        else:
            flags &= ~hint
        was_visible = win.isVisible()
        win.setWindowFlags(flags)
        if was_visible:
            win.show()

def _init_aot(win) -> None:
    """Apply current always_on_top config to a freshly created window."""
    try:
        if _cfg.get("always_on_top", True):
            win.setWindowFlags(win.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
    except Exception:
        pass

def open_settings() -> None:
    global _settings_window
    if _settings_window is None:
        from ui.settings_window import SettingsWindow
        _settings_window = SettingsWindow(
            on_hotkey_changed=_on_hotkey_changed,
            on_clear_history=_clear_history,
            on_clear_pinned=_clear_pinned,
            on_cleanup_interval_changed=_update_cleanup_interval,
            on_open_at_cursor_changed=main_window.set_open_at_cursor,
            on_close_after_copy_changed=main_window.set_close_after_copy,
            on_always_on_top_changed=_apply_always_on_top,
            on_close_on_outside_changed=main_window.set_close_on_outside_click,
            on_startup_changed=lambda v: None,
            db=db,
            vault=vault,
            backup_manager=backup_manager,
        )
        _init_aot(_settings_window)
    main_window.register_sibling_window(_settings_window)
    _settings_window.show()
    _settings_window.raise_()
    _settings_window.activateWindow()

# Donate window (lazy — imported on first use)
_donate_window = None

def open_donate() -> None:
    global _donate_window
    if _donate_window is None:
        from ui.donate_window import DonateWindow
        _donate_window = DonateWindow()
        _init_aot(_donate_window)
    # Ensure it never opens maximised / full-screen
    if _donate_window.isMaximized() or _donate_window.isFullScreen():
        _donate_window.showNormal()
    _donate_window.resize(600, 720)
    main_window.register_sibling_window(_donate_window)
    _donate_window.show()
    _donate_window.raise_()
    _donate_window.activateWindow()

# Help window (lazy — imported on first use)
_help_window = None

def open_help() -> None:
    global _help_window
    if _help_window is None:
        from ui.help_window import HelpWindow
        _help_window = HelpWindow()
        _init_aot(_help_window)
    main_window.register_sibling_window(_help_window)
    _help_window.show()
    _help_window.raise_()
    _help_window.activateWindow()

# Tray
tray = VeilClipTray(
    on_open=lambda: QTimer.singleShot(0, main_window.show_window),
    on_settings=open_settings,
    on_donate=open_donate,
    on_help=open_help,
    on_clear=None,
    on_exit=app.quit,
)
tray.show()

# Clipboard monitor — 0.3 s polling for instant updates (#1)
def _on_new_clip(item: dict) -> None:
    logger.debug("New clip [%s] '%s'", item["content_type"],
                 (item.get("content_text") or "")[:50])
    QTimer.singleShot(0, lambda: main_window.notify_new_item(item))

monitor = ClipboardMonitor(db, on_new_item=_on_new_clip, interval=0.3)
monitor.start()

# Hotkey
hotkey_manager = HotkeyManager()

def _safe_toggle():
    QTimer.singleShot(0, main_window.toggle)

hotkey_manager.register(DEFAULT_HOTKEY, _safe_toggle)
logger.info("Hotkey registered: %s", DEFAULT_HOTKEY)

# Action helpers
def _clear_history() -> None:
    removed = db.clear_unpinned()
    tray.show_message(APP_NAME, i18n.get("notifications.history_cleared"))
    main_window.refresh_items()
    logger.info("History cleared — %s item(s).", removed)

def _clear_pinned() -> None:
    db.clear_pinned()
    main_window.refresh_items()

def _on_hotkey_changed(new_hotkey: str) -> None:
    hotkey_manager.change_hotkey(new_hotkey, _safe_toggle)
    tray.show_message(
        APP_NAME,
        i18n.get("notifications.hotkey_changed", hotkey=new_hotkey.upper()),
    )

tray._on_clear = _clear_history

# Cleanup scheduler
_cleanup_hours:   int  = AUTO_DELETE_HOURS
_cleanup_enabled: bool = AUTO_DELETE_ENABLED
_CLEANUP_MS = 5 * 60 * 1000   # 5 minutes

def _run_cleanup() -> None:
    if not _cleanup_enabled:
        return
    removed = db.cleanup_old_items(max_age_hours=_cleanup_hours)
    if removed:
        logger.info("Scheduled cleanup: removed %s item(s).", removed)
        main_window.refresh_items()
        tray.show_message(
            APP_NAME,
            i18n.get("notifications.auto_cleanup_removed", count=removed),
        )

def _update_cleanup_interval(hours: int, enabled: bool) -> None:
    global _cleanup_hours, _cleanup_enabled
    _cleanup_hours, _cleanup_enabled = hours, enabled
    logger.info("Cleanup: %sh, enabled=%s", hours, enabled)
    _run_cleanup()

_cleanup_timer = QTimer()
_cleanup_timer.setInterval(_CLEANUP_MS)
_cleanup_timer.timeout.connect(_run_cleanup)
_cleanup_timer.start()
QTimer.singleShot(0, _run_cleanup)

# Shutdown
def _shutdown() -> None:
    logger.info("Shutting down…")
    _cleanup_timer.stop()
    hotkey_manager.unregister()
    monitor.stop()
    db.close()
    tray.hide()

app.aboutToQuit.connect(_shutdown)

logger.info("VeilClip running. Press %s to open.", DEFAULT_HOTKEY.upper())
tray.show_message(APP_NAME, i18n.get("notifications.started"))

_force_show_window = "--show-window" in sys.argv[1:]

# First-run: auto-open the window after 2 seconds so new users see it immediately
if _force_show_window or _cfg.get("first_run", False):
    QTimer.singleShot(2000, main_window.show_window)
    logger.info("Startup window open requested — window will open automatically.")

sys.exit(app.exec())
