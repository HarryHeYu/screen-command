"""外部能力 Provider 架构（产品定义第 21 节）。

core 不依赖任何具体外部服务：
- TranslationProvider / LLMProvider 目前只有抽象接口，**没有捆绑任何实现**——
  项目不强依赖付费 API，也不允许在未向用户明确提示的情况下联网（隐私要求）。
- 未来接入 local / OpenAI / DeepSeek / Gemini 时，实现对应接口并注册即可，
  Action 与 UI 层无需改动。
- 所有依赖外部 provider 的 action 在 provider 缺失时必须优雅降级
  （显示 "此动作需要 provider"），而不是让程序不可用。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class TranslationResult:
    text: str
    source_lang: str = ""
    target_lang: str = ""
    provider: str = ""


class TranslationProvider(ABC):
    """翻译能力抽象。实现必须自带超时与错误处理，禁止无提示上传。"""

    name: str = "abstract"

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def translate(
        self, text: str, target_lang: str = "zh", source_lang: str | None = None
    ) -> TranslationResult: ...


@dataclass
class LLMResult:
    text: str
    provider: str = ""
    model: str = ""
    elapsed_ms: float = 0.0
    data: dict = field(default_factory=dict)


class LLMProvider(ABC):
    """LLM 能力抽象（Explain / 未来的 Formula、Table 等作为可选增强）。"""

    name: str = "abstract"

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def complete(self, prompt: str, system: str | None = None) -> LLMResult: ...


def make_translation_provider() -> TranslationProvider | None:
    """返回当前配置的翻译 provider；未配置时返回 None（动作层据此降级）。"""
    return None


def make_llm_provider() -> LLMProvider | None:
    """返回当前配置的 LLM provider；未配置时返回 None（动作层据此降级）。"""
    return None
