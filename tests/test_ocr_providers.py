"""OCR provider 测试：mock 必过；Windows 真实 OCR 为集成测试（本地 win32 跑）。"""

from __future__ import annotations

import sys

import pytest

from screen_command.ocr import OcrError, make_provider
from screen_command.ocr.base import OCRProvider
from screen_command.ocr.mock import MockOcrProvider


@pytest.fixture(scope="module")
def provider():
    p = make_provider("windows")
    if not p.is_available():
        pytest.skip("Windows OCR unavailable")
    return p


class TestMockProvider:
    def test_recognize_returns_configured_text(self):
        p = MockOcrProvider("hello\nworld")
        r = p.recognize(b"\x89PNG fake")
        assert r.text == "hello\nworld"
        assert r.lines == ["hello", "world"]
        assert r.provider == "mock"

    def test_is_available(self):
        assert MockOcrProvider().is_available()


class TestProviderFactory:
    def test_mock_by_name(self):
        assert isinstance(make_provider("mock"), MockOcrProvider)

    def test_auto_returns_provider(self):
        assert isinstance(make_provider("auto"), OCRProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(OcrError):
            make_provider("no-such-provider")


class TestWordBoxExtraction:
    """词包围盒提取：兼容 winrt Rect 的小写字段，并据此重建缩进。"""

    class _Rect:
        def __init__(self, x, y, w, h):
            self.x = x
            self.y = y
            self.width = w
            self.height = h

    class _Word:
        def __init__(self, text, rect):
            self.text = text
            self.bounding_rect = rect

    class _Line:
        def __init__(self, words):
            self.words = words
            self.text = " ".join(w.text for w in words)

    class _Ocr:
        def __init__(self, lines):
            self.lines = lines

    def test_rect_reads_lowercase_fields(self):
        from screen_command.ocr.windows_ocr import _rect

        assert _rect(self._Rect(1, 2, 3, 4)) == (1, 2, 3, 4)

    def test_rect_reads_pascal_case_fields(self):
        from screen_command.ocr.windows_ocr import _rect

        class PascalRect:
            X, Y, Width, Height = 5, 6, 7, 8

        assert _rect(PascalRect()) == (5, 6, 7, 8)

    def test_word_boxes_extracted(self):
        from screen_command.ocr.windows_ocr import _word_boxes

        line = self._Line([self._Word("hi", self._Rect(10, 20, 30, 15))])
        boxes = _word_boxes(self._Ocr([line]))
        assert boxes[0][0].text == "hi"
        assert (boxes[0][0].x0, boxes[0][0].x1) == (10, 40)
        assert (boxes[0][0].y0, boxes[0][0].y1) == (20, 35)

    def test_indent_reconstructed_from_boxes(self):
        from screen_command.ocr.windows_ocr import _lines_with_indent

        lines = self._Ocr([
            self._Line([self._Word("def", self._Rect(10, 0, 30, 15))]),
            self._Line([self._Word("return", self._Rect(40, 20, 60, 15))]),
        ])
        out = _lines_with_indent(lines)
        assert out[0] == "def"
        assert out[1] == "   return"  # (40-10)/10 = 3 字符缩进


def test_windows_provider_uses_constructor_language():
    """CLI --language / 构造参数必须真正选引擎，不能只写进结果标签。"""
    from screen_command.ocr.windows_ocr import WindowsOcrProvider

    class Stub(WindowsOcrProvider):
        async def _recognize_async(self, image_png, language):
            chosen = language or self._preferred
            raise OcrError(f"chosen:{chosen}")

    with pytest.raises(OcrError, match="chosen:en-US"):
        Stub(language="en-US").recognize(b"x")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows OCR only")
class TestWindowsOcrIntegration:
    """真实识别测试 —— 依赖系统 en-US / zh-Hans-CN 语言包（本机已确认）。"""

    @staticmethod
    def _png(path) -> bytes:
        return path.read_bytes()

    def test_english(self, provider, fixtures):
        r = provider.recognize(self._png(fixtures["en_paragraph.png"]))
        t = " ".join(r.text.lower().split())
        assert "quick brown fox" in t
        assert "user location" in t

    def test_chinese(self, provider, fixtures):
        r = provider.recognize(self._png(fixtures["zh_paragraph.png"]))
        assert "机器学习" in r.text
        assert "深度学习" in r.text

    def test_mixed(self, provider, fixtures):
        r = provider.recognize(self._png(fixtures["mixed.png"]))
        assert "Python" in r.text or "python" in r.text.lower()
        assert "92.5" in r.text

    def test_dark_terminal_error(self, provider, fixtures):
        r = provider.recognize(self._png(fixtures["terminal_error.png"]))
        assert "Traceback" in r.text
        assert "RuntimeError" in r.text or "CUDA" in r.text

    def test_code(self, provider, fixtures):
        r = provider.recognize(self._png(fixtures["code.png"]))
        assert "def train" in r.text
        assert "model.train" in r.text or "model . train" in r.text

    def test_small_text(self, provider, fixtures):
        r = provider.recognize(self._png(fixtures["small_text.png"]))
        assert "annotation" in r.text.lower()

    def test_word_boxes_available(self, provider, fixtures):
        """锁定 winrt Rect 小写字段修复：真实识别必须给出词包围盒。"""
        r = provider.recognize(self._png(fixtures["en_paragraph.png"]))
        assert r.word_boxes
        assert all(w.text for row in r.word_boxes for w in row)

    def test_bad_image_raises(self, provider):
        with pytest.raises(OcrError):
            provider.recognize(b"not a png at all")

    def test_explicit_language(self, provider, fixtures):
        r = provider.recognize(self._png(fixtures["zh_paragraph.png"]),
                               language="zh-Hans-CN")
        assert "损失函数" in r.text

    def test_missing_language_pack_raises(self, provider, fixtures):
        with pytest.raises(OcrError):
            provider.recognize(self._png(fixtures["en_paragraph.png"]),
                               language="xx-YY")
