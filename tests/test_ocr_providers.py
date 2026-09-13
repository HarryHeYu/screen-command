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
