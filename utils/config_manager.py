"""
Thread-safe config manager backed by the per-user AppData config file.
"""

import json
import logging
import threading
from pathlib import Path

from utils.runtime import config_path, legacy_config_path, load_effective_config

logger = logging.getLogger(__name__)

_CFG_PATH = config_path("VeilClip")
_LEGACY_CFG_PATH = legacy_config_path()


class _ConfigManager:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def all(self) -> dict:
        with self._lock:
            return self._read()

    def get(self, key: str, default=None):
        return self.all().get(key, default)

    def set(self, key: str, value) -> None:
        with self._lock:
            data = self._read()
            data[key] = value
            self._write(data)

    def update(self, patch: dict) -> None:
        with self._lock:
            data = self._read()
            data.update(patch)
            self._write(data)

    def delete(self, key: str) -> None:
        with self._lock:
            data = self._read()
            data.pop(key, None)
            self._write(data)

    def _read(self) -> dict:
        try:
            return load_effective_config(self._path, _LEGACY_CFG_PATH)
        except Exception as exc:
            logger.warning("ConfigManager read failed: %s", exc)
        return {}

    def _write(self, data: dict) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("ConfigManager write failed: %s", exc)


cfg = _ConfigManager(_CFG_PATH)
