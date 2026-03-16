"""
core/backup.py
──────────────
Automatic database backup for VeilClip.

Copies the live SQLite database file to a user-chosen folder at a
configurable interval (in hours).  Keeps only the last N backups to
avoid filling disk.

Thread-safety: _run() is called from a QTimer on the Qt main thread,
so no locking is needed beyond SQLite's own WAL mode.
"""

import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import utils.i18n as i18n
from utils.config_manager import cfg as _cfg

logger = logging.getLogger(__name__)

# Default settings
DEFAULT_BACKUP_DIR   = ""   # empty = disabled
DEFAULT_BACKUP_HOURS = 24   # interval in hours
DEFAULT_BACKUP_KEEP  = 7    # number of backups to retain


class BackupManager:
    """
    Manages scheduled DB backups.

    Parameters
    ----------
    db_path : Path
        Path to the live SQLite database file.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._timer   = None   # QTimer, set up in start()

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the backup timer (must be called on the Qt main thread)."""
        from PyQt6.QtCore import QTimer
        self._timer = QTimer()
        self._timer.timeout.connect(self._run)
        self._reschedule()
        # Also run once at startup if overdue
        self._run_if_overdue()

    def stop(self) -> None:
        if self._timer:
            self._timer.stop()

    def run_now(self) -> tuple[bool, str]:
        """
        Force an immediate backup.
        Returns (success, message).
        """
        return self._do_backup()

    def update_settings(
        self,
        backup_dir: str,
        hours: int,
        keep: int,
    ) -> None:
        """Called from settings when the user changes backup config."""
        _cfg.update({
            "backup_dir":   backup_dir,
            "backup_hours": hours,
            "backup_keep":  keep,
        })
        self._reschedule()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _settings(self) -> tuple[str, int, int]:
        d    = _cfg.get("backup_dir",   DEFAULT_BACKUP_DIR)
        h    = int(_cfg.get("backup_hours", DEFAULT_BACKUP_HOURS))
        keep = int(_cfg.get("backup_keep",  DEFAULT_BACKUP_KEEP))
        return d, max(1, h), max(1, keep)

    def _reschedule(self) -> None:
        if self._timer is None:
            return
        d, hours, _ = self._settings()
        if not d:
            self._timer.stop()
            return
        self._timer.setInterval(hours * 3600 * 1000)
        self._timer.start()
        logger.debug("Backup timer: every %sh → %s", hours, d)

    def _run(self) -> None:
        d, _, _ = self._settings()
        if not d:
            return
        ok, msg = self._do_backup()
        if ok:
            logger.info("Backup: %s", msg)
        else:
            logger.warning("Backup failed: %s", msg)

    def _run_if_overdue(self) -> None:
        """Run a backup now if the last backup is older than the interval."""
        d, hours, _ = self._settings()
        if not d:
            return
        backup_dir = Path(d)
        existing = sorted(backup_dir.glob("veilclip_backup_*.db"))
        if existing:
            last_mtime = existing[-1].stat().st_mtime
            age_h = (time.time() - last_mtime) / 3600
            if age_h < hours:
                return   # recent enough
        self._run()

    def _do_backup(self) -> tuple[bool, str]:
        d, _, keep = self._settings()
        if not d:
            return False, i18n.get("backup.messages.no_directory")
        backup_dir = Path(d)
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            return False, i18n.get("backup.messages.create_dir_failed", detail=str(exc))

        if not self._db_path.exists():
            return False, i18n.get("backup.messages.db_missing", path=str(self._db_path))

        ts   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dest = backup_dir / f"veilclip_backup_{ts}.db"
        try:
            shutil.copy2(str(self._db_path), str(dest))
        except Exception as exc:
            return False, i18n.get("backup.messages.copy_failed", detail=str(exc))

        # Prune old backups
        all_backups = sorted(backup_dir.glob("veilclip_backup_*.db"))
        while len(all_backups) > keep:
            try:
                all_backups.pop(0).unlink()
            except Exception:
                break

        return True, i18n.get("backup.messages.completed", filename=dest.name)
