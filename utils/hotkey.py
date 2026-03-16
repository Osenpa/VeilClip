from __future__ import annotations

import ctypes
import logging
import threading
from ctypes import wintypes
from typing import Callable

from utils.config import DEFAULT_HOTKEY

logger = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
PM_NOREMOVE = 0x0000

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT),
        ("lPrivate", wintypes.DWORD),
    ]


_KEY_ALIASES: dict[str, int] = {
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "pause": 0x13,
    "capslock": 0x14,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "pageup": 0x21,
    "pgup": 0x21,
    "pagedown": 0x22,
    "pgdn": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "printscreen": 0x2C,
    "insert": 0x2D,
    "delete": 0x2E,
    "del": 0x2E,
    "0": 0x30,
    "1": 0x31,
    "2": 0x32,
    "3": 0x33,
    "4": 0x34,
    "5": 0x35,
    "6": 0x36,
    "7": 0x37,
    "8": 0x38,
    "9": 0x39,
    "backspace": 0x08,
}

for code in range(ord("A"), ord("Z") + 1):
    _KEY_ALIASES[chr(code).lower()] = code

for i in range(1, 25):
    _KEY_ALIASES[f"f{i}"] = 0x6F + i


def _parse_hotkey(hotkey_str: str) -> tuple[int, int]:
    parts = [part.strip().lower() for part in hotkey_str.split("+") if part.strip()]
    if not parts:
        raise ValueError("Hotkey is empty.")

    mods = MOD_NOREPEAT
    vk: int | None = None

    for part in parts:
        if part in {"ctrl", "control"}:
            mods |= MOD_CONTROL
            continue
        if part == "alt":
            mods |= MOD_ALT
            continue
        if part == "shift":
            mods |= MOD_SHIFT
            continue
        if part in {"win", "meta", "super"}:
            mods |= MOD_WIN
            continue
        if vk is not None:
            raise ValueError(f"Unsupported hotkey '{hotkey_str}'.")
        vk = _KEY_ALIASES.get(part)
        if vk is None:
            raise ValueError(f"Unsupported key '{part}'.")

    if vk is None:
        raise ValueError(f"Hotkey '{hotkey_str}' does not include a main key.")

    return mods, vk


class HotkeyManager:
    """Global hotkey registration using Windows RegisterHotKey."""

    def __init__(self) -> None:
        self._current_hotkey: str | None = None
        self._hotkey_id = 0xBEEF
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._callback: Callable | None = None
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._register_ok = False

    def register(
        self,
        hotkey_str: str = DEFAULT_HOTKEY,
        callback: Callable | None = None,
    ) -> bool:
        if not callback:
            logger.warning("register() called with no callback, skipping.")
            return False

        self.unregister()

        try:
            mods, vk = _parse_hotkey(hotkey_str)
        except ValueError as exc:
            logger.error("Failed to parse hotkey '%s': %s", hotkey_str, exc)
            return False

        self._callback = callback
        self._stop_event.clear()
        self._ready_event.clear()
        self._register_ok = False

        self._thread = threading.Thread(
            target=self._message_loop,
            args=(mods, vk),
            name="GlobalHotkey",
            daemon=True,
        )
        self._thread.start()
        self._ready_event.wait(timeout=2)

        if not self._register_ok:
            self.unregister()
            return False

        self._current_hotkey = hotkey_str
        logger.info("Hotkey registered: '%s'", hotkey_str)
        return True

    def unregister(self) -> None:
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            if self._thread_id:
                user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            self._thread.join(timeout=2)
        if self._current_hotkey:
            logger.info("Hotkey unregistered: '%s'", self._current_hotkey)
        self._thread = None
        self._thread_id = None
        self._callback = None
        self._current_hotkey = None
        self._register_ok = False

    def change_hotkey(self, new_hotkey_str: str, callback: Callable) -> bool:
        logger.info("Changing hotkey: '%s' -> '%s'", self._current_hotkey, new_hotkey_str)
        return self.register(new_hotkey_str, callback)

    @property
    def current_hotkey(self) -> str | None:
        return self._current_hotkey

    @property
    def is_registered(self) -> bool:
        return self._current_hotkey is not None

    def _message_loop(self, mods: int, vk: int) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()
        msg = MSG()

        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_NOREMOVE)

        if not user32.RegisterHotKey(None, self._hotkey_id, mods, vk):
            err = ctypes.get_last_error()
            logger.error("Failed to register hotkey (mods=%s, vk=%s), error=%s", mods, vk, err)
            self._ready_event.set()
            return

        self._register_ok = True
        self._ready_event.set()

        try:
            while not self._stop_event.is_set():
                result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result in (0, -1):
                    break
                if msg.message == WM_HOTKEY and msg.wParam == self._hotkey_id and self._callback:
                    try:
                        self._callback()
                    except Exception as exc:
                        logger.error("Hotkey callback failed: %s", exc)
        finally:
            user32.UnregisterHotKey(None, self._hotkey_id)


def get_cursor_position() -> tuple[int, int]:
    try:
        import win32api

        x, y = win32api.GetCursorPos()
        return (x, y)
    except Exception:
        pass

    try:
        from PyQt6.QtGui import QCursor

        pos = QCursor.pos()
        return (pos.x(), pos.y())
    except Exception:
        pass

    logger.warning("get_cursor_position: all methods failed, returning (0, 0).")
    return (0, 0)
