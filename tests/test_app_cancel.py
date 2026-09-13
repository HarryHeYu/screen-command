"""AppController 取消与状态守卫单测（不 show 窗口、不抓屏幕）。"""

from __future__ import annotations

import pytest

from screen_command.actions.base import ActionContext, ActionResult


@pytest.fixture
def controller(qapp):
    from screen_command.app import AppController

    c = AppController()
    yield c
    c.status.close()


class TestCancelProcessing:
    def test_cancel_returns_to_idle(self, controller):
        from screen_command.app import PROCESSING

        controller._ctx = ActionContext(image_png=b"x")
        controller.state = PROCESSING
        controller._cancel_processing()
        assert controller.state == "idle"

    def test_cancel_sets_token(self, controller):
        from screen_command.app import PROCESSING
        import threading

        controller._ctx = ActionContext(image_png=b"x")
        controller.state = PROCESSING
        controller._ctx.cancel_token = threading.Event()
        controller._cancel_processing()
        assert controller._ctx.cancel_token.is_set()

    def test_cancel_outside_processing_is_noop(self, controller):
        from screen_command.app import IDLE

        controller.state = IDLE
        controller._cancel_processing()
        assert controller.state == IDLE

    def test_stale_result_dropped(self, controller):
        """取消后迟到的结果不得把状态机拉回 SHOWING。"""
        from screen_command.app import PROCESSING

        controller._ctx = ActionContext(image_png=b"x")
        controller.state = PROCESSING
        controller._cancel_processing()
        controller._on_action_done(ActionResult("ocr", ok=True, text="late"))
        assert controller.state == "idle"

    def test_quick_flag_not_set_when_busy(self, controller):
        """P1-1 回归：忙时按 Quick 热键不得置位 _pending_quick。"""
        from screen_command.app import PROCESSING

        controller.state = PROCESSING
        controller.start_quick_capture()
        assert controller._pending_quick is False
        assert controller.state == PROCESSING
