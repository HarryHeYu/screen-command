"""Mock provider：无 GUI / 无 WinRT / 自动化测试环境跑通整条 pipeline。"""

from __future__ import annotations

from .base import OcrResult, OCRProvider


class MockOcrProvider(OCRProvider):
    name = "mock"

    def __init__(self, text: str = "mock recognized text\n第二行中文内容") -> None:
        self.text = text

    def is_available(self) -> bool:
        return True

    @property
    def languages(self) -> list[str]:
        return ["mock"]

    def recognize(self, image_png: bytes, language: str | None = None) -> OcrResult:
        import zlib

        return OcrResult(
            text=self.text,
            lines=self.text.splitlines(),
            language=language or "mock",
            provider=self.name,
            width_px=len(image_png),
            height_px=zlib.crc32(image_png) % 4096,
        )
