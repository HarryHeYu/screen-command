"""OCRProvider 抽象。

UI 与 Action 只依赖这里的接口与数据类型，不 import 任何具体实现
（具体 provider 由 `screen_command.ocr` 的工厂函数按需装配）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class OcrResult:
    text: str
    lines: list[str] = field(default_factory=list)
    language: str = ""
    provider: str = ""
    width_px: int = 0
    height_px: int = 0
    elapsed_ms: float = 0.0

    @property
    def empty(self) -> bool:
        return not self.text.strip()


class OCRProvider(ABC):
    """所有 OCR 后端的统一接口。recognize() 接收 PNG 字节流，返回结构化结果。"""

    name: str = "abstract"

    @abstractmethod
    def is_available(self) -> bool:
        """后端是否可用于当前环境（不抛异常）。"""

    @abstractmethod
    def recognize(self, image_png: bytes, language: str | None = None) -> OcrResult:
        """识别 PNG 图片字节流。

        language: BCP-47 标签（如 "zh-Hans-CN"）；None 表示由 provider 自行决定。
        识别失败时抛出 OcrError。
        """

    @property
    @abstractmethod
    def languages(self) -> list[str]:
        """可用的识别语言标签列表。"""


class OcrError(RuntimeError):
    pass
