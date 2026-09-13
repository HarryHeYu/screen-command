"""AppController：状态机与全流程编排。

    Idle → Capturing → ChoosingAction → Processing → ShowingResult → Idle

所有 UI 转移集中在这里，overlay / menu / result 互不直接通信。
OCR 等动作在 QThreadPool 后台线程执行，UI 不冻结，结果经信号回主线程。
"""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, QRect, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication

from . import capture
from .actions.base import Action, ActionContext, ActionResult
from .actions.builtin import CopyTextAction
from .hotkey import GlobalHotkeyThread
from .logutil import Timer, get_logger
from .overlay import OverlayWindow
from .providers import make_llm_provider, make_translation_provider
from .ui.action_menu import ActionMenu
from .ui.result_window import ResultWindow
from .ui.status_window import StatusWindow

log = get_logger()

IDLE = "idle"
CAPTURING = "capturing"
CHOOSING = "choosing-action"
PROCESSING = "processing"
SHOWING = "showing-result"


class _JobSignals(QObject):
    done = Signal(object)  # ActionResult


class _ActionJob(QRunnable):
    def __init__(self, fn, signals: _JobSignals, action_id: str) -> None:
        super().__init__()
        self._fn = fn
        self._signals = signals
        self._action_id = action_id

    def run(self) -> None:  # 后台线程
        try:
            result = self._fn()
        except Exception as exc:  # noqa: BLE001 — 后台线程兜底，UI 不崩
            log.exception("action job crashed")
            result = ActionResult(self._action_id, ok=False, error=str(exc))
        self._signals.done.emit(result)


class _HotkeyBridge(QObject):
    triggered = Signal()


class AppController(QObject):
    def __init__(self) -> None:
        super().__init__()
        from .ocr import make_provider

        self.state = IDLE
        self._provider = make_provider("auto")
        from .actions import build_default_actions

        self._actions = build_default_actions(
            self._provider,
            translation_provider=make_translation_provider(),
            llm_provider=make_llm_provider(),
        )
        self._quick_copy = CopyTextAction(self._provider)  # Quick Action: 框选→OCR→复制
        self._pending_quick = False
        self._engine = capture  # CaptureCore 模块函数集

        self._snapshots: list[capture.ScreenSnapshot] = []
        self._overlays: list[OverlayWindow] = []
        self._region: QRect | None = None
        self._ctx: ActionContext | None = None
        self._current_action: Action | None = None
        self._result_win: ResultWindow | None = None
        self._active_signals: _JobSignals | None = None

        self.status = StatusWindow()
        self.status.capture_requested.connect(self.start_capture)
        self.status.quit_requested.connect(self.shutdown)

        self._menu: ActionMenu | None = None
        self._hotkey: GlobalHotkeyThread | None = None
        self._hotkey_bridge = _HotkeyBridge()
        self._hotkey_bridge.triggered.connect(self.start_capture)
        self._quick_bridge = _HotkeyBridge()
        self._quick_bridge.triggered.connect(self.start_quick_capture)
        self._pool = QThreadPool.globalInstance()

    # -- lifecycle ---------------------------------------------------------

    def run(self) -> None:
        self.status.show()
        self._hotkey = GlobalHotkeyThread({
            "ctrl+shift+a": self._hotkey_bridge.triggered.emit,
            "ctrl+shift+1": self._quick_bridge.triggered.emit,
        })
        self._hotkey.start()
        self._watch_hotkey()

    def _watch_hotkey(self) -> None:
        from PySide6.QtCore import QTimer

        def check() -> None:
            if self._hotkey and self._hotkey.ok:
                self.status.set_hotkey_ok(True)
            elif self._hotkey and not self._hotkey.is_alive():
                self.status.set_hotkey_ok(False)
            else:
                QTimer.singleShot(300, check)

        QTimer.singleShot(300, check)

    def shutdown(self) -> None:
        self._cancel_all()
        if self._hotkey:
            self._hotkey.stop()
        QApplication.quit()

    # -- capture -----------------------------------------------------------

    @Slot()
    def start_quick_capture(self) -> None:
        """Quick Action：框选 → OCR → 复制，不弹菜单（产品定义第 25 节）。"""
        # 必须先确认本次触发真的会进入框选，否则标志会泄漏到下一次普通框选
        if self.state not in (IDLE, SHOWING):
            return
        self._pending_quick = True
        self.start_capture()

    @Slot()
    def start_capture(self) -> None:
        if self.state not in (IDLE, SHOWING):
            self._pending_quick = False
            return
        if self._result_win:
            self._result_win.close()
            self._result_win = None
        try:
            with Timer() as t:
                self._snapshots = capture.snapshot_all_screens()
            self.state = CAPTURING
            self.status.set_status("框选屏幕区域，Esc 取消")
            for snap in self._snapshots:
                ov = OverlayWindow(snap)
                ov.finished.connect(self._on_selection)
                ov.cancelled.connect(self._on_capture_cancelled)
                ov.open_overlay()
                self._overlays.append(ov)
        except Exception:  # noqa: BLE001 — 异常时回滚到 Idle，避免状态卡死
            log.exception("start_capture failed")
            self._close_overlays()
            self._snapshots = []
            self._pending_quick = False
            self.state = IDLE
            self.status.set_status("捕获失败 — 详见日志")
            return
        # 键盘焦点给光标所在屏
        cursor_pos = QCursor.pos()
        for ov in self._overlays:
            if ov.geometry().contains(cursor_pos):
                ov.activateWindow()
                ov.setFocus(Qt.FocusReason.OtherFocusReason)
                break
        log.info("state: capturing (overlay up in %.1f ms)", t.ms)

    def _on_capture_cancelled(self) -> None:
        self._close_overlays()
        self._snapshots = []
        self._pending_quick = False
        self.state = IDLE
        self.status.set_status("已取消 — Ctrl+Shift+A 重新框选")
        log.info("state: idle (capture cancelled)")

    def _close_overlays(self) -> None:
        for ov in self._overlays:
            ov.close()
        self._overlays.clear()

    # -- selection → menu --------------------------------------------------

    def _on_selection(self, global_rect: QRect) -> None:
        self._close_overlays()
        self._region = global_rect

        screen = capture.screen_for_global_point(
            global_rect.center().x(), global_rect.center().y()
        )
        snap = next(
            (s for s in self._snapshots if s.screen is screen), self._snapshots[0]
        )
        pm = capture.crop_snapshot(snap, global_rect)
        png = capture.pixmap_to_png_bytes(pm)
        log.info(
            "capture: region %dx%d@(%d,%d) on %s → %d KB png",
            pm.width(), pm.height(), global_rect.x(), global_rect.y(),
            screen.name(), len(png) // 1024,
        )

        self._ctx = ActionContext(
            image_png=png,
            image=pm.toImage(),
            region=global_rect,
            screen_label=screen.name(),
        )
        self.state = CHOOSING
        self._current_action = None
        # 全屏快照用完即弃（隐私 + 内存：N 块屏的全分辨率位图不留到下一轮）
        self._snapshots = []
        if self._pending_quick:
            self._pending_quick = False
            self.status.set_status("Quick OCR → 复制…")
            self._run_action(self._quick_copy)
            return
        self.status.set_status("选择动作…")
        self._menu = ActionMenu(self._actions)
        self._menu.action_selected.connect(self._run_action)
        self._menu.cancelled.connect(self._on_menu_cancelled)
        # 弹在选区右上角
        gx = global_rect.x() + global_rect.width() + 12
        gy = global_rect.y()
        self._menu.popup_at(gx, gy, screen.geometry())

    def _on_menu_cancelled(self) -> None:
        if self.state != CHOOSING:
            return  # 菜单 hide 可能在其他状态由组合路径触发，勿回拉状态机
        self._pending_quick = False
        self.state = IDLE
        self.status.set_status("已取消 — Ctrl+Shift+A 重新框选")

    # -- action execution --------------------------------------------------

    def _run_action(self, action: Action) -> None:
        if self.state != CHOOSING or self._ctx is None:
            return
        self._current_action = action
        # GUI 交互必须在主线程：保存截图的路径选择在这里完成，动作体只负责写文件
        if action.id == "save_image" and "output_path" not in self._ctx.options:
            from PySide6.QtWidgets import QFileDialog

            suggested = time.strftime("capture-%Y%m%d-%H%M%S.png")
            path, _ = QFileDialog.getSaveFileName(
                self.status, "保存截图", suggested, "PNG (*.png)"
            )
            if not path:
                self.state = IDLE
                self.status.set_status("已取消保存 — Ctrl+Shift+A 重新框选")
                return
            self._ctx.options["output_path"] = path

        self.state = PROCESSING
        self.status.set_status(f"执行 {action.name} …")
        log.info("action %s: start", action.id)

        signals = _JobSignals()
        # 主线程持引用：防止 worker 线程结束时 signals 被析构、queued 信号丢失
        # （否则状态机会间歇性卡死在 PROCESSING，P1-2）
        self._active_signals = signals
        signals.done.connect(self._on_action_done)
        ctx = self._ctx
        self._pool.start(
            _ActionJob(lambda: action.execute(ctx), signals, action.id)
        )

    def _on_action_done(self, result: ActionResult) -> None:
        self._active_signals = None
        log.info(
            "action %s: done ok=%s in %.0f ms", result.action_id, result.ok, result.elapsed_ms
        )
        if self.state != PROCESSING:
            return
        # QClipboard 只能在主线程使用 —— 动作在 worker 线程只留下意图标记
        if result.ok and result.data.get("copy_to_clipboard"):
            QApplication.clipboard().setText(result.text)
            result.data["copied"] = True
        self.state = SHOWING
        self.status.set_status("完成 — 关闭结果窗或按 Ctrl+Shift+A 重新框选")
        if self._result_win is None:
            self._result_win = ResultWindow()
            self._result_win.retry_requested.connect(self._retry_last)
            self._result_win.rerun_requested.connect(self._rerun_menu)
            self._result_win.closed.connect(self._on_result_closed)
        self._result_win.show_result(result)

    def _on_result_closed(self) -> None:
        if self.state == SHOWING:
            self.state = IDLE
            self.status.set_status("就绪 — Ctrl+Shift+A 框选，Ctrl+Shift+1 快速复制")

    def _retry_last(self) -> None:
        if self._current_action and self._ctx:
            self.state = CHOOSING
            self._run_action(self._current_action)

    def _rerun_menu(self) -> None:
        if self._ctx is None:
            return
        self.state = CHOOSING
        self.status.set_status("选择动作…")
        self._menu = ActionMenu(self._actions)
        self._menu.action_selected.connect(self._run_action)
        self._menu.cancelled.connect(self._on_menu_cancelled)
        screen = QGuiApplication.primaryScreen()
        self._menu.popup_at(self.status.x() + 40, self.status.y() + 80, screen.geometry())

    def _cancel_all(self) -> None:
        self._close_overlays()
        if self._menu:
            self._menu.close()
            self._menu = None
