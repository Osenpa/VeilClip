from pathlib import Path

from utils.runtime import (
    appdata_root,
    config_path,
    legacy_config_path,
    load_effective_config,
    resource_path,
)


APP_NAME = "VeilClip"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Osenpa"
APP_TITLE = "VeilClip - Open-Source Offline Clipboard Manager for Windows"
APP_DESCRIPTION = "Open-source offline clipboard manager for Windows"


APP_DIR = appdata_root(APP_NAME)
DATA_DIR = APP_DIR / "data"
LOG_DIR = APP_DIR / "logs"
CONFIG_FILE = config_path(APP_NAME)
LEGACY_CONFIG_FILE = legacy_config_path()
ASSETS_DIR = resource_path("assets")
ICONS_DIR = ASSETS_DIR


def get_db_path() -> Path:
    """Return the active DB path, honoring packaged install defaults."""
    config = load_effective_config(CONFIG_FILE, LEGACY_CONFIG_FILE)
    custom_path = config.get("db_path")
    if custom_path:
        return Path(custom_path)
    return DATA_DIR / "data.db"


DB_PATH = get_db_path()
DB_TIMEOUT_SEC = 10


DEFAULT_HOTKEY = "alt+v"


MAX_ITEMS = 100
MAX_ITEM_SIZE = 15 * 1024 * 1024


AUTO_DELETE_HOURS = 24
AUTO_DELETE_ENABLED = True


WINDOW_WIDTH = 480
WINDOW_HEIGHT = 600
WINDOW_OPACITY = 0.97
MAX_PREVIEW_CHARS = 200
MAX_PREVIEW_HEIGHT = 80


ICON_APP = ASSETS_DIR / "icon.png"
ICON_TRAY = ASSETS_DIR / "icon.ico"
ICON_TRAY_DARK = ASSETS_DIR / "icon.ico"


DEFAULT_LANGUAGE = "en"
LOCALE_DIR = resource_path("locales")
LOCALE_FILE = LOCALE_DIR / f"{DEFAULT_LANGUAGE}.json"


LOG_FILE = LOG_DIR / "veilclip.log"
LOG_MAX_BYTES = 2 * 1024 * 1024
LOG_BACKUP_COUNT = 3
LOG_LEVEL = "INFO"


def ensure_dirs() -> None:
    for directory in (APP_DIR, DATA_DIR, LOG_DIR, CONFIG_FILE.parent):
        directory.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    ensure_dirs()
    print("-" * 40)
    print(f"  {APP_NAME} v{APP_VERSION}")
    print("-" * 40)
    print(f"  App directory   : {APP_DIR}")
    print(f"  Config file     : {CONFIG_FILE}")
    print(f"  Database        : {DB_PATH}")
    print(f"  Hotkey          : {DEFAULT_HOTKEY.upper()}")
    print(f"  Max items       : {MAX_ITEMS}")
    print(f"  Max item size   : {MAX_ITEM_SIZE // (1024 * 1024)} MB")
    print(f"  Auto delete     : {AUTO_DELETE_HOURS} hours")
    print(f"  Assets          : {ASSETS_DIR}")
    print(f"  Locale file     : {LOCALE_FILE}")
    print("-" * 40)
