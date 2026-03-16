"""
core/clipboard_monitor.py
─────────────────────────
Background thread that polls the system clipboard every 300 ms and
saves new items to the database.

Fix #1 — Instant update
────────────────────────
The monitor now calls on_new_item immediately after saving.  The caller
(main.py) wraps the callback in QTimer.singleShot(0, ...) so the Qt UI
refreshes on the main thread without delay.
"""

import hashlib
import io
import logging
import sys
import threading
import time
from pathlib import Path
from typing import Callable

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

import win32clipboard
import win32con
from PIL import Image

from utils.config import MAX_ITEM_SIZE

logger = logging.getLogger(__name__)

CF_DIB         = win32con.CF_DIB
CF_HDROP       = win32con.CF_HDROP
CF_UNICODETEXT = win32con.CF_UNICODETEXT


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ClipboardMonitor:
    """
    Polls the clipboard in a daemon thread.

    Parameters
    ----------
    db          : Database      Open database instance.
    on_new_item : callable      Called with the saved item dict on every new entry.
                                Runs on the monitor thread — marshal to Qt main
                                thread with QTimer.singleShot(0, ...) in the caller.
    interval    : float         Poll interval in seconds (default 0.3 s).
    """

    def __init__(
        self,
        db,
        on_new_item: Callable[[dict], None] | None = None,
        interval: float = 0.3,
    ) -> None:
        self._db          = db
        self._on_new_item = on_new_item
        self._interval    = interval
        self._last_hash   = ""
        self._stop_event  = threading.Event()
        self._thread: threading.Thread | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        # Pre-seed the hash with whatever is currently on the clipboard so the
        # very first poll never saves it as a "new" item.  This prevents VeilClip
        # from capturing stale CMD/terminal content that was already on the
        # clipboard before the app launched.
        self._seed_initial_hash()
        self._thread = threading.Thread(
            target=self._loop,
            name="ClipboardMonitor",
            daemon=True,
        )
        self._thread.start()
        logger.info("ClipboardMonitor started (interval=%.2fs).", self._interval)

    def _seed_initial_hash(self) -> None:
        """Read the current clipboard and record its hash without saving to DB.

        Called once before the monitor thread starts so that existing clipboard
        content is never treated as a new item on the first poll.
        """
        try:
            win32clipboard.OpenClipboard()
            try:
                _, raw_bytes, _ = self._read_clipboard()
                if raw_bytes:
                    self._last_hash = _sha256(raw_bytes)
                    logger.debug("ClipboardMonitor: seeded initial hash (len=%d)", len(raw_bytes))
            finally:
                try:
                    win32clipboard.CloseClipboard()
                except Exception:
                    pass
        except Exception as exc:
            logger.debug("ClipboardMonitor: seed failed (non-fatal): %s", exc)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("ClipboardMonitor stopped.")

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ── Loop ──────────────────────────────────────────────────────────────────

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._poll()
            except Exception as exc:
                logger.debug("Clipboard poll error: %s", exc)
            self._stop_event.wait(self._interval)

    def _poll(self) -> None:
        try:
            win32clipboard.OpenClipboard()
        except Exception:
            return

        try:
            content_type, raw_bytes, meta = self._read_clipboard()
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass

        if content_type is None or not raw_bytes:
            return

        # Hash dedup — skip silently if clipboard unchanged
        current_hash = _sha256(raw_bytes)
        if current_hash == self._last_hash:
            return
        self._last_hash = current_hash

        # Size guard
        if len(raw_bytes) > MAX_ITEM_SIZE:
            logger.warning("Clipboard item too large (%s B) — skipped.", len(raw_bytes))
            return

        # Source filter — ignore clipboard changes triggered by the VeilClip
        # launcher process itself (python.exe, pythonw.exe, cmd.exe, etc.)
        source = meta.get("source_app", "") or ""
        _LAUNCHER_NAMES = {
            "python", "pythonw", "python3",
            "cmd", "command prompt",
            "powershell", "pwsh",
            "windows powershell",
        }
        if source.lower().split(".")[0] in _LAUNCHER_NAMES:
            logger.debug("Skipping clipboard item from launcher source: %s", source)
            return

        # Persist
        kwargs: dict = {"source_app": meta.get("source_app")}
        if content_type == "image":
            kwargs["content_blob"] = raw_bytes
        else:
            kwargs["content_text"] = meta.get("text", "")

        item_id = self._db.add_item(content_type, len(raw_bytes), **kwargs)
        if item_id is None:
            return   # duplicate in DB or size exceeded — already logged

        # Build item dict and notify immediately
        item = {
            "id":           item_id,
            "content_type": content_type,
            "content_text": kwargs.get("content_text"),
            "content_blob": kwargs.get("content_blob"),
            "source_app":   meta.get("source_app"),
            "is_pinned":    0,
            "size_bytes":   len(raw_bytes),
        }
        logger.debug(
            "Saved %s — id=%s size=%sB source='%s'",
            content_type, item_id, len(raw_bytes), meta.get("source_app"),
        )
        if self._on_new_item:
            try:
                self._on_new_item(item)
            except Exception as exc:
                logger.error("on_new_item callback raised: %s", exc)

    # ── Clipboard reading ─────────────────────────────────────────────────────

    def _read_clipboard(self) -> tuple[str | None, bytes | None, dict]:
        meta: dict = {"source_app": self._get_source_app()}

        # Image (DIB)
        if win32clipboard.IsClipboardFormatAvailable(CF_DIB):
            try:
                dib_data  = win32clipboard.GetClipboardData(CF_DIB)
                png_bytes = self._dib_to_png(dib_data)
                if png_bytes:
                    return "image", png_bytes, meta
            except Exception as exc:
                logger.debug("DIB read failed: %s", exc)

        # File paths (HDROP)
        if win32clipboard.IsClipboardFormatAvailable(CF_HDROP):
            try:
                paths = win32clipboard.GetClipboardData(CF_HDROP)
                if paths:
                    text = "\n".join(paths)
                    meta["text"] = text
                    return "filepath", text.encode("utf-8", errors="replace"), meta
            except Exception as exc:
                logger.debug("HDROP read failed: %s", exc)

        # Unicode text
        if win32clipboard.IsClipboardFormatAvailable(CF_UNICODETEXT):
            try:
                text = win32clipboard.GetClipboardData(CF_UNICODETEXT)
                if text and text.strip():
                    meta["text"] = text
                    stripped = text.strip()
                    if stripped.startswith(("http://", "https://", "ftp://")):
                        ctype = "link"
                        # Enrich source with domain name
                        domain = self._extract_domain(stripped)
                        if domain:
                            meta["source_app"] = domain
                    else:
                        ctype = "text"
                    return ctype, text.encode("utf-8", errors="replace"), meta
            except Exception as exc:
                logger.debug("Unicode text read failed: %s", exc)

        return None, None, meta

    @staticmethod
    def _extract_domain(url: str) -> str | None:
        """Return a human-readable domain from a URL, e.g. 'github.com'."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            host   = parsed.netloc or parsed.path
            # Strip www.
            host = host.removeprefix("www.")
            # Keep only the domain part (drop port)
            host = host.split(":")[0]
            return host if host else None
        except Exception:
            return None

    @staticmethod
    def _dib_to_png(dib_data: bytes) -> bytes | None:
        try:
            import struct
            bfh_size  = 14
            file_size = bfh_size + len(dib_data)
            pix_off   = struct.unpack_from("<I", dib_data, 0)[0] + bfh_size
            header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, pix_off)
            img = Image.open(io.BytesIO(header + dib_data))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as exc:
            logger.debug("DIB→PNG failed: %s", exc)
            return None

    @staticmethod
    def _get_source_app() -> str:
        try:
            from core.source_detector import get_active_app_name
            return get_active_app_name()
        except Exception:
            return "Unknown"


# ── Quick test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from core.database import Database
    from utils.config  import DB_PATH, LOCALE_DIR
    import utils.i18n  as i18n

    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s")
    i18n.init(LOCALE_DIR)

    db  = Database(db_path=DB_PATH)
    db.init_db()

    def _cb(item):
        print(f"  ★ [{item['content_type']}] id={item['id']} src='{item['source_app']}'")

    mon = ClipboardMonitor(db, on_new_item=_cb)
    mon.start()
    print("Monitoring 20 s — copy something!")
    time.sleep(20)
    mon.stop()
