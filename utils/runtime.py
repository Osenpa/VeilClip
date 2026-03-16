from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


_APPDATA_FALLBACK = Path.home() / "AppData" / "Roaming"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def install_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return project_root()


def bundle_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return install_root()


def resource_path(*parts: str) -> Path:
    return bundle_root().joinpath(*parts)


def appdata_root(app_name: str) -> Path:
    base = os.getenv("APPDATA")
    return Path(base) / app_name if base else _APPDATA_FALLBACK / app_name


def config_path(app_name: str) -> Path:
    return appdata_root(app_name) / "config.json"


def legacy_config_path() -> Path:
    return project_root() / "config.json"


def install_defaults_path() -> Path:
    return install_root() / "install_defaults.json"


def load_json_file(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def load_install_defaults() -> dict[str, Any]:
    return load_json_file(install_defaults_path())


def load_effective_config(primary_path: Path, legacy_path: Path | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {}
    data.update(load_install_defaults())
    if legacy_path and legacy_path != primary_path:
        data.update(load_json_file(legacy_path))
    data.update(load_json_file(primary_path))
    return data


def relaunch_command(args: list[str] | None = None) -> list[str]:
    extra_args = list(sys.argv[1:] if args is None else args)
    if is_frozen():
        return [str(Path(sys.executable)), *extra_args]
    return [sys.executable, str(project_root() / "main.py"), *extra_args]


def startup_dir() -> Path:
    base = Path(os.getenv("APPDATA")) if os.getenv("APPDATA") else _APPDATA_FALLBACK
    return base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def startup_shortcut_path(app_name: str) -> Path:
    return startup_dir() / f"{app_name}.lnk"


def startup_shortcut_details() -> tuple[str, str, str]:
    command = relaunch_command(args=[])
    target = str(Path(command[0]))
    arguments = subprocess.list2cmdline(command[1:]) if len(command) > 1 else ""
    working_dir = str(install_root() if is_frozen() else project_root())
    return target, arguments, working_dir


def startup_command() -> str:
    return subprocess.list2cmdline(relaunch_command(args=[]))
