"""状态窗 / 结果窗的纯 UI 行为（不抓屏、不跑 OCR）。"""

from __future__ import annotations

import pytest

from screen_command.actions.base import ActionResult
from screen_command.ui.result_window import ResultWindow
from screen_command.ui.status_window import StatusWindow


@pytest.mark.usefixtures("qapp")
class TestStatusWindow:
    def test_partial_hotkey_failure_names_the_missing_combo(self):
        w = StatusWindow()
        w.set_hotkey_status({"alt+w"}, "alt+w", "alt+x")
        text = w._status.text()
        assert "ALT+X" in text
        assert "失败" in text
        w.close()

    def test_all_hotkeys_ok_shows_ready(self):
        w = StatusWindow()
        w.set_hotkey_status({"alt+w", "alt+x"}, "alt+w", "alt+x")
        assert "就绪" in w._status.text()
        w.close()


@pytest.mark.usefixtures("qapp")
class TestResultWindow:
    def test_copy_button_uses_primary_object_name(self):
        w = ResultWindow()
        assert w._btn_copy.objectName() == "rPrimary"
        w.close()

    def test_failure_disables_copy_and_edit(self):
        w = ResultWindow()
        w.show_result(ActionResult("ocr", ok=False, error="boom"))
        assert not w._btn_copy.isEnabled()
        assert not w._btn_edit.isEnabled()
        w.close()

    def test_success_enables_copy(self):
        w = ResultWindow()
        w.show_result(ActionResult("ocr", ok=True, text="hello"))
        assert w._btn_copy.isEnabled()
        assert w._btn_edit.isEnabled()
        w.close()
