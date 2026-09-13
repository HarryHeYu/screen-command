"""全局快捷键：运行期 RegisterHotKey（进程存活期有效，退出即释放）。

组合键字符串（如 "ctrl+alt+q"）由 parse_combo 通用解析，默认值见 config.py，
用户可在项目根目录 config.toml 的 [hotkey] 段覆盖。
不写注册表、不改系统快捷键设置，程序关闭后系统不留任何痕迹。
注册失败（如快捷键被占用）不阻塞核心链路，GUI 按钮仍可用。
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import threading
from typing import Callable

from .logutil import get_logger

log = get_logger()

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

_MOD_MAP = {"ctrl": MOD_CONTROL, "shift": MOD_SHIFT, "alt": MOD_ALT, "win": MOD_WIN}


def parse_combo(combo: str) -> tuple[int, int]:
    """'ctrl+alt+q' → (mods, vk)。支持 1–2 个 ctrl/shift/alt/win + 单个字母或数字。"""
    parts = [p.strip().lower() for p in combo.split("+")]
    if len(parts) not in (2, 3):
        raise ValueError(f"invalid combo {combo!r}: expected 'mod+key' or 'mod+mod+key'")
    *mods_raw, key = parts
    mods = MOD_NOREPEAT
    for m in mods_raw:
        if m not in _MOD_MAP:
            raise ValueError(f"unknown modifier {m!r} in {combo!r}")
        mods |= _MOD_MAP[m]
    if len(key) == 1 and key.isalnum():
        return mods, ord(key.upper())
    raise ValueError(f"unsupported key {key!r} in {combo!r} (letter/digit only)")


class GlobalHotkeyThread(threading.Thread):
    """在独立 Win32 消息循环线程中注册并监听多组全局快捷键。

    combos: {组合键字符串: callback}，callback 在热键线程被调用——
    跨线程使用时请通过 Qt Signal（线程安全）转发。
    """

    def __init__(self, combos: dict[str, Callable[[], None]]) -> None:
        super().__init__(daemon=True, name="hotkey")
        self._combos = {k.lower(): v for k, v in combos.items()}
        self._callbacks: dict[int, Callable[[], None]] = {}
        self._registered: set[str] = set()
        self._thread_id: int | None = None
        self._ready = threading.Event()
        self.stop_event = threading.Event()

    @property
    def ok(self) -> bool:
        return bool(self._registered)

    @property
    def registered_combos(self) -> set[str]:
        return set(self._registered)

    def run(self) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._thread_id = kernel32.GetCurrentThreadId()

        for i, (combo, cb) in enumerate(self._combos.items()):
            try:
                mods, vk = parse_combo(combo)
            except ValueError as exc:
                log.error("hotkey: %s", exc)
                continue
            hotkey_id = 0xB000 + i
            if user32.RegisterHotKey(None, hotkey_id, mods, vk):
                self._callbacks[hotkey_id] = cb
                self._registered.add(combo)
                log.info("hotkey: %s registered (process-lifetime only)", combo)
            else:
                log.error(
                    "hotkey: RegisterHotKey(%s) failed (winerror %s) — GUI 按钮仍可用",
                    combo, ctypes.get_last_error(),
                )
        self._ready.set()
        if not self._callbacks:
            return

        msg = ctypes.wintypes.MSG()
        # 阻塞 GetMessage：热键触发零延迟、线程空转零功耗；
        # stop() 通过 PostThreadMessage(WM_QUIT) 唤醒本循环
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam in self._callbacks:
                try:
                    self._callbacks[msg.wParam]()
                except Exception:  # noqa: BLE001 — 热键线程绝不向主程序抛异常
                    log.exception("hotkey: callback error")
            elif msg.message == WM_QUIT:
                break

        for hotkey_id in self._callbacks:
            user32.UnregisterHotKey(None, hotkey_id)
        log.info("hotkey: unregistered %d combo(s)", len(self._callbacks))

    def stop(self) -> None:
        self.stop_event.set()
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
