"""全局快捷键：运行期 RegisterHotKey（进程存活期有效，退出即释放）。

支持多组快捷键（如 Ctrl+Shift+A 框选、Ctrl+Shift+1 快速 OCR+复制）。
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

_PRESETS = {
    "ctrl+shift+a": (MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, 0x41),  # 'A'
    "ctrl+shift+1": (MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, 0x31),  # '1'
}


class GlobalHotkeyThread(threading.Thread):
    """在独立 Win32 消息循环线程中注册并监听多组全局快捷键。

    combos: {"ctrl+shift+a": callback, ...}，callback 在热键线程被调用——
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
            if combo not in _PRESETS:
                log.error("hotkey: unknown combo %r", combo)
                continue
            hotkey_id = 0xB000 + i
            mods, vk = _PRESETS[combo]
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
            ctypes.windll.user32.PostThreadMessageW(
                self._thread_id, WM_QUIT, 0, 0
            )
