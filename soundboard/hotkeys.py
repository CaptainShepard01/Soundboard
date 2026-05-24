"""
hotkeys.py — System-wide hotkeys via Win32 RegisterHotKey.

Unlike the `keyboard` library, RegisterHotKey distinguishes numpad digits
(num0–num9) from regular digit keys via separate VK codes (VK_NUMPAD0–9).

Registered with hwnd=NULL so WM_HOTKEY goes to the calling thread's queue.
HotkeyManager is a QAbstractNativeEventFilter installed on QApplication —
Qt's event loop delivers WM_HOTKEY to nativeEventFilter regardless of which
window (if any) has focus.

Hotkey string format (case-insensitive, parts joined with '+'):
  Modifiers : ctrl  alt  shift  win
  Letters   : a–z
  Digits    : 0–9
  Numpad    : num0–num9  num*  num+  num-  num/  num.
  F-keys    : f1–f12
  Other     : space enter tab backspace delete insert
              home end pageup pagedown up down left right escape
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
from typing import Callable

from PyQt6.QtCore import QAbstractNativeEventFilter

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.RegisterHotKey.argtypes = [
    ctypes.wintypes.HWND, ctypes.c_int,
    ctypes.wintypes.UINT, ctypes.wintypes.UINT,
]
_user32.RegisterHotKey.restype = ctypes.wintypes.BOOL
_user32.UnregisterHotKey.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
_user32.UnregisterHotKey.restype = ctypes.wintypes.BOOL

MOD_ALT      = 0x0001
MOD_CONTROL  = 0x0002
MOD_SHIFT    = 0x0004
MOD_WIN      = 0x0008
MOD_NOREPEAT = 0x4000

_VK: dict[str, int] = {
    # Letters
    **{c: ord(c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"},
    # Regular digits
    **{str(i): 0x30 + i for i in range(10)},
    # Numpad digits (VK_NUMPAD0=0x60 … VK_NUMPAD9=0x69)
    **{f"NUM{i}": 0x60 + i for i in range(10)},
    # Numpad operators
    "NUM*": 0x6A, "NUM+": 0x6B, "NUM-": 0x6D, "NUM.": 0x6E, "NUM/": 0x6F,
    # F-keys (VK_F1=0x70 … VK_F12=0x7B)
    **{f"F{i}": 0x6F + i for i in range(1, 13)},
    # Common keys
    "SPACE":     0x20, "ENTER":    0x0D, "TAB":       0x09,
    "BACKSPACE": 0x08, "DELETE":   0x2E, "INSERT":    0x2D,
    "HOME":      0x24, "END":      0x23, "PAGEUP":    0x21,
    "PAGEDOWN":  0x22, "UP":       0x26, "DOWN":      0x28,
    "LEFT":      0x25, "RIGHT":    0x27, "ESCAPE":    0x1B, "ESC": 0x1B,
}

_VK_NAME: dict[int, str] = {}
for _k, _v in _VK.items():
    if _v not in _VK_NAME:
        _VK_NAME[_v] = _k.lower()


def parse_hotkey(s: str) -> tuple[int, int]:
    """Return (modifier_flags, vk_code). Returns (0, 0) on failure."""
    mods, vk = 0, 0
    for part in s.upper().replace(" ", "").split("+"):
        if part in ("CTRL", "CONTROL"):
            mods |= MOD_CONTROL
        elif part == "ALT":
            mods |= MOD_ALT
        elif part == "SHIFT":
            mods |= MOD_SHIFT
        elif part in ("WIN", "WINDOWS", "META"):
            mods |= MOD_WIN
        else:
            vk = _VK.get(part, 0)
    return mods, vk


class HotkeyManager(QAbstractNativeEventFilter):
    """
    Registers thread-wide global hotkeys (hwnd=NULL) and catches WM_HOTKEY
    via QAbstractNativeEventFilter installed on the QApplication.
    """

    def __init__(self) -> None:
        super().__init__()
        self._next_id = 100
        self._id_to_cb: dict[int, Callable] = {}
        self._key_to_id: dict[str, int] = {}

    def register(self, hotkey: str, callback: Callable[[], None]) -> bool:
        if not hotkey:
            return False
        mods, vk = parse_hotkey(hotkey)
        if not vk:
            print(f"[HotkeyManager] Unrecognised key in '{hotkey}'")
            return False
        self.unregister(hotkey)
        hk_id = self._next_id
        self._next_id += 1
        # hwnd=0 → WM_HOTKEY posted to calling thread's queue
        ok = bool(_user32.RegisterHotKey(0, hk_id, mods | MOD_NOREPEAT, vk))
        if not ok:
            print(f"[HotkeyManager] RegisterHotKey failed for '{hotkey}' "
                  f"(error {ctypes.get_last_error()})")
            return False
        self._id_to_cb[hk_id] = callback
        self._key_to_id[hotkey] = hk_id
        return True

    def unregister(self, hotkey: str) -> None:
        hk_id = self._key_to_id.pop(hotkey, None)
        if hk_id is not None:
            _user32.UnregisterHotKey(0, hk_id)
            self._id_to_cb.pop(hk_id, None)

    def unregister_all(self) -> None:
        for hotkey in list(self._key_to_id):
            self.unregister(hotkey)

    def dispatch(self, hk_id: int) -> None:
        cb = self._id_to_cb.get(hk_id)
        if cb:
            cb()

    def nativeEventFilter(self, event_type: bytes, message) -> tuple[bool, int]:
        if event_type == b"windows_generic_MSG":
            addr = int(message)
            if addr:
                msg = ctypes.wintypes.MSG.from_address(addr)
                if msg.message == 0x0312:  # WM_HOTKEY
                    self.dispatch(int(msg.wParam))
                    return True, 0
        return False, 0

    @property
    def active_hotkeys(self) -> list[str]:
        return list(self._key_to_id.keys())
