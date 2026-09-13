"""Action 层测试：结构化结果、注册表、保存落盘、无 GUI 剪贴板守卫。"""

from __future__ import annotations

from pathlib import Path

import pytest

from screen_command.actions import (
    Action,
    ActionContext,
    ActionResult,
    CopyTextAction,
    OCRAction,
    SaveImageAction,
    all_actions,
    build_default_actions,
)
from screen_command.ocr import MockOcrProvider


@pytest.fixture
def provider():
    return MockOcrProvider("line one\nline two 中文")


class TestOCRAction:
    def test_ok_and_text(self, provider):
        r = OCRAction(provider).execute(ActionContext(image_png=b"img"))
        assert r.ok
        assert r.action_id == "ocr"
        assert "line one" in r.text
        assert r.data["provider"] == "mock"
        assert r.elapsed_ms >= 0

    def test_missing_image(self, provider):
        r = OCRAction(provider).execute(ActionContext())
        assert not r.ok
        assert r.error

    def test_provider_failure_is_contained(self):
        class Boom:
            name = "boom"

            def is_available(self):
                return True

            def recognize(self, png, language=None):
                raise RuntimeError("boom")

        r = OCRAction(Boom()).execute(ActionContext(image_png=b"x"))  # type: ignore[arg-type]
        assert not r.ok
        assert "boom" in (r.error or "")


class TestCopyTextAction:
    def test_returns_clipboard_intent_for_main_thread(self, provider):
        """QClipboard 只能在主线程使用 —— 动作只产出意图标记，由 AppController 落地。"""
        r = CopyTextAction(provider).execute(ActionContext(image_png=b"img"))
        assert r.ok
        assert "line one" in r.text
        assert r.data["copy_to_clipboard"] is True
        assert "copied" not in r.data  # copied 由主线程实际写入后追加


class TestSaveImageAction:
    def test_saves_png_bytes(self, provider, tmp_path: Path):
        out = tmp_path / "cap.png"
        r = SaveImageAction().execute(
            ActionContext(image_png=b"\x89PNGdata",
                          options={"output_path": str(out)})
        )
        assert r.ok
        assert out.read_bytes() == b"\x89PNGdata"
        assert r.data["path"] == str(out)

    def test_no_image(self):
        r = SaveImageAction().execute(ActionContext(options={"output_path": "x.png"}))
        assert not r.ok


class TestRegistry:
    def test_build_default_actions(self, provider):
        from screen_command.actions import clear_actions

        clear_actions()
        actions = build_default_actions(provider)
        ids = [a.id for a in actions]
        assert ids == ["ocr", "copy_text", "translate", "code", "markdown",
                       "explain", "save_image"]
        assert all(isinstance(a, Action) for a in actions)

    def test_all_actions_registered(self, provider):
        from screen_command.actions import clear_actions

        clear_actions()
        build_default_actions(provider)
        assert {a.id for a in all_actions()} >= {
            "ocr", "copy_text", "translate", "code", "markdown", "explain", "save_image",
        }


def test_result_is_structured():
    r = ActionResult("ocr", ok=True, text="x", markdown=None, data={"k": 1})
    assert r.data == {"k": 1} and r.markdown is None
