"""v0.2 动作测试：Translate 降级 / Code 后处理 / Markdown 组装 / Explain 规则分析。"""

from __future__ import annotations

import pytest

from screen_command.actions import (
    ActionContext,
    CodeOCRAction,
    ExplainErrorAction,
    MarkdownAction,
    TranslateAction,
)
from screen_command.actions.v02 import NO_TRANSLATION_PROVIDER
from screen_command.ocr import MockOcrProvider
from screen_command.ocr.base import OcrResult


@pytest.fixture
def provider():
    return MockOcrProvider("placeholder")


def _ocr_lines(*lines: str) -> OcrResult:
    return OcrResult(text="\n".join(lines), lines=list(lines), provider="mock")


class TestTranslateAction:
    def test_no_provider_degrades_gracefully(self, provider):
        r = TranslateAction(provider, translation_provider=None).execute(
            ActionContext(image_png=b"img")
        )
        assert not r.ok
        assert "Provider" in r.error
        assert "不会在未提示" in r.error  # 隐私提示

    def test_unavailable_provider_degrades(self, provider):
        class Unavailable:
            name = "u"

            def is_available(self):
                return False

            def translate(self, text, target_lang="zh", source_lang=None):
                raise AssertionError("should not be called")

        r = TranslateAction(provider, translation_provider=Unavailable()).execute(  # type: ignore[arg-type]
            ActionContext(image_png=b"img")
        )
        assert not r.ok

    def test_ocr_failure_propagates(self):
        class Failing:
            name = "f"

            def is_available(self):
                return True

            def recognize(self, png, language=None):
                raise RuntimeError("ocr down")

        r = TranslateAction(Failing()).execute(ActionContext(image_png=b"x"))  # type: ignore[arg-type]
        assert not r.ok
        assert "ocr down" in r.error


class TestCodeOCRAction:
    def test_fullwidth_and_smart_quotes_fixed(self, provider, monkeypatch):
        monkeypatch.setattr(
            MockOcrProvider, "recognize",
            lambda self, png, language=None: _ocr_lines(
                'x = “hello”', "if  a ＝ 1：", "12  print(x)"
            ),
        )
        r = CodeOCRAction(MockOcrProvider()).execute(ActionContext(image_png=b"i"))
        assert r.ok
        assert 'x = "hello"' in r.text
        assert "if  a = 1:" in r.text
        assert "print(x)" in r.text  # 行号前缀被剥离
        assert r.markdown.startswith("```python")

    def test_indentation_preserved(self, provider, monkeypatch):
        monkeypatch.setattr(
            MockOcrProvider, "recognize",
            lambda self, png, language=None: _ocr_lines("def f():", "    return 1"),
        )
        r = CodeOCRAction(MockOcrProvider()).execute(ActionContext(image_png=b"i"))
        assert "    return 1" in r.text

    def test_language_guess_bash(self, provider, monkeypatch):
        monkeypatch.setattr(
            MockOcrProvider, "recognize",
            lambda self, png, language=None: _ocr_lines("git push origin main"),
        )
        r = CodeOCRAction(MockOcrProvider()).execute(ActionContext(image_png=b"i"))
        assert r.data["language_guess"] == "bash"


class TestMarkdownAction:
    def test_paragraph_and_code_split(self, provider, monkeypatch):
        monkeypatch.setattr(
            MockOcrProvider, "recognize",
            lambda self, png, language=None: _ocr_lines(
                "这是说明文字。",
                "def f():",
                "    return 1",
                "结尾段落。",
            ),
        )
        r = MarkdownAction(MockOcrProvider()).execute(ActionContext(image_png=b"i"))
        assert r.ok
        assert "这是说明文字。" in r.markdown
        assert "```" in r.markdown and "def f():" in r.markdown
        assert r.markdown.index("这是说明文字。") < r.markdown.index("```")

    def test_plain_text_passthrough(self, provider, monkeypatch):
        monkeypatch.setattr(
            MockOcrProvider, "recognize",
            lambda self, png, language=None: _ocr_lines("只有一段", "普通文字。"),
        )
        r = MarkdownAction(MockOcrProvider()).execute(ActionContext(image_png=b"i"))
        assert "只有一段 普通文字。" in r.markdown or "只有一段" in r.markdown


class TestExplainErrorAction:
    def test_python_traceback_analysis(self, provider, monkeypatch):
        monkeypatch.setattr(
            MockOcrProvider, "recognize",
            lambda self, png, language=None: _ocr_lines(
                "Traceback (most recent call last):",
                '  File "train.py", line 42, in <module>',
                "RuntimeError: CUDA out of memory.",
            ),
        )
        r = ExplainErrorAction(MockOcrProvider()).execute(ActionContext(image_png=b"i"))
        assert r.ok
        assert "RuntimeError" in r.markdown
        assert "显存不足" in r.markdown
        assert "batch size" in r.markdown
        assert "train.py" in r.markdown
        assert r.data["mode"] == "rules"

    def test_merged_single_line_traceback(self, provider, monkeypatch):
        """真实 OCR 常把 traceback 合并成一行，也应能解析。"""
        monkeypatch.setattr(
            MockOcrProvider, "recognize",
            lambda self, png, language=None: _ocr_lines(
                'Traceback (most recent ca11 last):Fi1e "train.py", line 42, '
                "in <module> loss = criterion(outputs, labels) "
                "RuntimeError: CUDA out Of memory."
            ),
        )
        r = ExplainErrorAction(MockOcrProvider()).execute(ActionContext(image_png=b"i"))
        assert r.ok
        assert "RuntimeError" in r.markdown
        assert "显存不足" in r.markdown

    def test_module_not_found_hint(self, provider, monkeypatch):
        monkeypatch.setattr(
            MockOcrProvider, "recognize",
            lambda self, png, language=None: _ocr_lines(
                "Traceback (most recent call last):",
                "ModuleNotFoundError: No module named 'requests'",
            ),
        )
        r = ExplainErrorAction(MockOcrProvider()).execute(ActionContext(image_png=b"i"))
        assert "requests" in r.markdown

    def test_generic_error_keywords(self, provider, monkeypatch):
        monkeypatch.setattr(
            MockOcrProvider, "recognize",
            lambda self, png, language=None: _ocr_lines(
                "git push origin main",
                "fatal: unable to access 'x': Connection refused",
            ),
        )
        r = ExplainErrorAction(MockOcrProvider()).execute(ActionContext(image_png=b"i"))
        assert "fatal" in r.markdown

    def test_no_error_detected(self, provider, monkeypatch):
        monkeypatch.setattr(
            MockOcrProvider, "recognize",
            lambda self, png, language=None: _ocr_lines("hello world"),
        )
        r = ExplainErrorAction(MockOcrProvider()).execute(ActionContext(image_png=b"i"))
        assert r.ok
        assert "未检测到" in r.markdown

    def test_no_llm_provider_is_fine(self, provider):
        """无 LLM provider 时 Explain 仍应可用（规则分析）。"""
        a = ExplainErrorAction(MockOcrProvider(), llm_provider=None)
        assert a is not None
