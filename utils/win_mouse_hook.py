"""
utils/win_mouse_hook.py
───────────────────────
Low-level Windows WH_MOUSE_LL hook (64-bit safe).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import threading
import time

logger = logging.getLogger(__name__)

WH_MOUSE_LL    = 14
WM_QUIT        = 0x0012
WM_LBUTTONDOWN = 0x0201
WM_RBUTTONDOWN = 0x0204
WM_MBUTTONDOWN = 0x0207
PM_REMOVE      = 0x0001

# 64-bit safe: lParam is a pointer → use c_longlong on 64-bit Windows
HOOKPROC = ctypes.CFUNCTYPE(
    ctypes.c_longlong,          # return type
    ctypes.c_int,               # nCode
    ctypes.wintypes.WPARAM,     # wParam  (UINT_PTR)
    ctypes.wintypes.LPARAM,     # lParam  (LONG_PTR  — signed 64-bit)
)

user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Set explicit argtypes/restype so ctypes marshals correctly on 64-bit
user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    HOOKPROC,
    ctypes.wintypes.HINSTANCE,
    ctypes.wintypes.DWORD,
]
user32.SetWindowsHookExW.restype = ctypes.wintypes.HHOOK

user32.CallNextHookEx.argtypes = [
    ctypes.wintypes.HHOOK,      # hhk  (may be NULL)
    ctypes.c_int,               # nCode
    ctypes.wintypes.WPARAM,     # wParam
    ctypes.wintypes.LPARAM,     # lParam
]
user32.CallNextHookEx.restype = ctypes.c_longlong

user32.UnhookWindowsHookEx.argtypes = [ctypes.wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype  = ctypes.wintypes.BOOL

user32.PeekMessageW.argtypes = [
    ctypes.POINTER(ctypes.wintypes.MSG),
    ctypes.wintypes.HWND,
    ctypes.wintypes.UINT,
    ctypes.wintypes.UINT,
    ctypes.wintypes.UINT,
]
user32.PeekMessageW.restype = ctypes.wintypes.BOOL

user32.PostThreadMessageW.argtypes = [
    ctypes.wintypes.DWORD,
    ctypes.wintypes.UINT,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
]
user32.PostThreadMessageW.restype = ctypes.wintypes.BOOL


class WinMouseHook:
    """Install WH_MOUSE_LL; call *callback* on every mouse-button-down."""

    def __init__(self, callback) -> None:
        self._callback = callback
        self._hook_id  = None
        self._tid: int = 0
        self._thread: threading.Thread | None = None
        self._ready    = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._ready.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="WinMouseHook"
        )
        self._thread.start()
        self._ready.wait(timeout=3.0)

    def stop(self) -> None:
        if self._tid:
            user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._tid = 0

    def _run(self) -> None:
        self._tid = kernel32.GetCurrentThreadId()

        def _proc(nCode: int, wParam: int, lParam: int) -> int:
            if nCode >= 0 and wParam in (
                WM_LBUTTONDOWN, WM_RBUTTONDOWN, WM_MBUTTONDOWN
            ):
                try:
                    self._callback()
                except Exception:
                    pass
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        self._c_proc = HOOKPROC(_proc)

        # WH_MOUSE_LL requires hMod = NULL
        self._hook_id = user32.SetWindowsHookExW(
            WH_MOUSE_LL, self._c_proc, None, 0
        )

        if not self._hook_id:
            err = kernel32.GetLastError()
            logger.warning("WinMouseHook: failed (error %d)", err)
            self._ready.set()
            return

        logger.debug("WinMouseHook: installed (id=%s)", self._hook_id)
        self._ready.set()

        msg = ctypes.wintypes.MSG()
        while True:
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                if msg.message == WM_QUIT:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.005)

        user32.UnhookWindowsHookEx(self._hook_id)
        self._hook_id = None
        logger.debug("WinMouseHook: uninstalled")
