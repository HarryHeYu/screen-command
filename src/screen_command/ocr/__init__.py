"""OCR 能力入口：provider 工厂。UI / CLI 只从这里获取 provider 实例。"""

from __future__ import annotations

import sys

from .base import OcrError, OcrResult, OCRProvider
from .mock import MockOcrProvider

__all__ = ["OCRProvider", "OcrResult", "OcrError", "make_provider", "MockOcrProvider"]


def make_provider(name: str = "auto", language: str | None = None) -> OCRProvider:
    """按名称构造 provider。

    auto: Windows 上优先系统内置 OCR，不可用时回退 mock（并保证 pipeline 可跑通）。
    windows: 强制使用系统内置 OCR，不可用则抛 OcrError。
    mock: 恒定 mock（测试用）。
    """
    if name == "mock":
        return MockOcrProvider()
    if name == "windows":
        from .windows_ocr import WindowsOcrProvider

        p = WindowsOcrProvider(language=language)
        if not p.is_available():
            raise OcrError("Windows OCR unavailable (no recognizer language packs?)")
        return p
    if name == "auto":
        if sys.platform == "win32":
            from .windows_ocr import WindowsOcrProvider

            p = WindowsOcrProvider(language=language)
            if p.is_available():
                return p
        return MockOcrProvider()
    raise OcrError(f"unknown provider: {name!r}")
