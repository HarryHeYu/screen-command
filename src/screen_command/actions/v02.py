"""v0.2 动作：Translate / Code OCR / Markdown / Explain Error。

设计约束：
- Translate 依赖外部 TranslationProvider；未配置时优雅降级（明确提示，绝不静默联网）。
- Code / Markdown / Explain 全部离线规则实现，Explain 的 LLM 增强仅是可选 hook。
"""

from __future__ import annotations

import re

from ..logutil import Timer, get_logger
from ..ocr.base import OcrError, OCRProvider
from ..providers import LLMProvider, TranslationProvider
from .base import Action, ActionContext, ActionResult
from .builtin import OCRAction

log = get_logger()

NO_TRANSLATION_PROVIDER = (
    "此动作需要翻译 Provider（当前未配置）。\n"
    "为遵守隐私约定，Screen Command 不会在未提示的情况下把内容发送到第三方服务。"
)

NO_LLM_PROVIDER = (
    "此动作的 AI 增强需要 LLM Provider（当前未配置）；已给出离线规则分析结果。"
)


class TranslateAction(Action):
    id = "translate"
    name = "翻译"
    hint = "OCR → 翻译"
    shortcut = "3"

    def __init__(
        self,
        ocr_provider: OCRProvider,
        translation_provider: TranslationProvider | None = None,
        target_lang: str = "zh",
    ) -> None:
        self.ocr_provider = ocr_provider
        self.translation_provider = translation_provider
        self.target_lang = target_lang

    def execute(self, ctx: ActionContext) -> ActionResult:
        ocr = OCRAction(self.ocr_provider).execute(ctx)
        if not ocr.ok:
            return ocr
        if not ocr.text.strip():
            return ActionResult(self.id, ok=False, error="OCR 未识别到文字")
        if self.translation_provider is None or not self.translation_provider.is_available():
            return ActionResult(self.id, ok=False, error=NO_TRANSLATION_PROVIDER, data=ocr.data)
        try:
            with Timer() as t:
                tr = self.translation_provider.translate(ocr.text, target_lang=self.target_lang)
            return ActionResult(
                self.id,
                ok=True,
                text=tr.text,
                data={**ocr.data, "translation_provider": tr.provider,
                      "target_lang": tr.target_lang},
                elapsed_ms=ocr.elapsed_ms + t.ms,
            )
        except Exception as exc:  # noqa: BLE001
            log.error("action translate: %s", exc)
            return ActionResult(self.id, ok=False, error=f"translation failed: {exc}")


# ---------------------------------------------------------------- code

# 代码上下文里常见的全角/智能标点污染
_CODE_CHAR_FIXES = {
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "‘": "'", "’": "'", "′": "'",
    "：": ":", "；": ";", "，": ",", "。": ".",
    "（": "(", "）": ")", "【": "[", "】": "]",
    "｛": "{", "｝": "}", "＝": "=", "＋": "+",
    "《": "<", "》": ">", "｜": "|", "　": " ",
}

_LINE_NUMBER = re.compile(r"^\s*(\d{1,4})[:|\s]\s+(?=\S)")


class CodeOCRAction(Action):
    """OCR → 代码后处理：保留缩进、修复全角/智能标点、剥离行号前缀。"""

    id = "code"
    name = "提取代码"
    hint = "OCR → 格式化代码"
    shortcut = "4"

    def __init__(self, ocr_provider: OCRProvider) -> None:
        self.ocr_provider = ocr_provider

    def execute(self, ctx: ActionContext) -> ActionResult:
        ocr = OCRAction(self.ocr_provider).execute(ctx)
        if not ocr.ok:
            return ocr
        lines = ocr.data.get("lines") or ocr.text.splitlines()
        fixed = []
        for line in lines:
            line = line.translate(str.maketrans(_CODE_CHAR_FIXES))
            line = _LINE_NUMBER.sub("", line, count=1)
            line = line.rstrip()
            fixed.append(line)
        # 去掉首尾空行，保留内部缩进
        while fixed and not fixed[0].strip():
            fixed.pop(0)
        while fixed and not fixed[-1].strip():
            fixed.pop()
        code = "\n".join(fixed)
        lang = self._guess_language(code)
        return ActionResult(
            self.id,
            ok=True,
            text=code,
            markdown=f"```{lang}\n{code}\n```",
            data={**ocr.data, "language_guess": lang},
            elapsed_ms=ocr.elapsed_ms,
        )

    @staticmethod
    def _guess_language(code: str) -> str:
        head = code.lstrip().lower()
        if (re.search(r"\bdef\s+\w+\s*\(", code) or "import " in head
                or re.search(r"\bprint\s*\(", code)):
            return "python"
        if re.search(r"#include|std::|int\s+main\s*\(", code):
            return "cpp"
        if re.search(r"\bfunction\b|=>|const\s|let\s", code):
            return "javascript"
        if re.search(r"^\s*\$\s|\becho\b|\bgit\b", head, re.MULTILINE):
            return "bash"
        return ""


# ---------------------------------------------------------------- markdown

_CODEY_LINE = re.compile(r"[{};=]|^\s{4,}|^\s*(def |class |import |from |return )")


class MarkdownAction(Action):
    """OCR → Markdown：代码感行组装为 fenced block，其余按段落。"""

    id = "markdown"
    name = "转 Markdown"
    hint = "OCR → Markdown"
    shortcut = "5"

    def __init__(self, ocr_provider: OCRProvider) -> None:
        self.ocr_provider = ocr_provider

    def execute(self, ctx: ActionContext) -> ActionResult:
        ocr = OCRAction(self.ocr_provider).execute(ctx)
        if not ocr.ok:
            return ocr
        lines = ocr.data.get("lines") or ocr.text.splitlines()
        md_parts: list[str] = []
        buf: list[str] = []

        def flush_paragraph() -> None:
            if buf:
                md_parts.append(" ".join(s.strip() for s in buf))
                buf.clear()

        code_buf: list[str] = []
        in_code = False

        def flush_code() -> None:
            nonlocal in_code
            if code_buf:
                md_parts.append("```\n" + "\n".join(code_buf) + "\n```")
                code_buf.clear()
            in_code = False

        for line in lines:
            if _CODEY_LINE.search(line):
                if not in_code:
                    flush_paragraph()
                    in_code = True
                code_buf.append(line)
            else:
                if in_code:
                    flush_code()
                if not line.strip():
                    flush_paragraph()
                else:
                    buf.append(line)
        flush_code()
        flush_paragraph()
        md = "\n\n".join(p for p in md_parts if p.strip())
        return ActionResult(
            self.id, ok=True, text=md, markdown=md,
            data=ocr.data, elapsed_ms=ocr.elapsed_ms,
        )


# ---------------------------------------------------------------- explain

_PY_LAST_LINE = re.compile(
    r"\b(\w+(?:\.\w+)*(?:Error|Exception|Warning|Interrupt))\s*[:：]\s*(.+)$"
)
_CUDA_OOM = re.compile(r"CUDA out of memory", re.IGNORECASE)

_KNOWN_ERRORS = {
    "ModuleNotFoundError": "导入的模块未安装或不在当前环境路径中",
    "ImportError": "模块存在但导入的名称缺失（可能是循环导入或版本不匹配）",
    "FileNotFoundError": "程序按给定路径找不到文件（相对路径可能基于错误的工作目录）",
    "PermissionError": "操作系统拒绝了访问（文件被占用 / 需要权限 / 只读位置）",
    "KeyError": "字典/映射中不存在请求的键",
    "IndexError": "序列索引越界（列表长度小于索引值）",
    "ValueError": "参数类型正确但取值不合法",
    "TypeError": "操作/函数收到了不匹配的类型或参数个数",
    "AttributeError": "对象没有该属性/方法（可能是 None 或类型不符）",
    "ZeroDivisionError": "除数为零",
    "SyntaxError": "代码语法不符合 Python 规则",
    "IndentationError": "缩进不一致",
    "ConnectionError": "网络连接失败",
    "TimeoutError": "操作超时",
    "OSError": "操作系统层错误（查看 errno / 子类信息）",
}


class ExplainErrorAction(Action):
    """错误解释：离线规则分析为主，LLM provider 可选增强。

    无 LLM 时照常给出规则分析（产品定义第 28 节：AI 可以作为增强）。
    """

    id = "explain"
    name = "解释错误"
    hint = "报错分析"
    shortcut = "6"

    def __init__(self, ocr_provider: OCRProvider, llm_provider: LLMProvider | None = None):
        self.ocr_provider = ocr_provider
        self.llm_provider = llm_provider

    def execute(self, ctx: ActionContext) -> ActionResult:
        ocr = OCRAction(self.ocr_provider).execute(ctx)
        if not ocr.ok:
            return ocr
        text = ocr.text
        md = self._rule_analysis(text)
        notes: list[str] = []
        if self.llm_provider is not None and self.llm_provider.is_available():
            notes.append("LLM 增强已配置但尚未接入（见 docs/DECISIONS.md）")
        else:
            notes.append("离线规则分析（未配置 LLM Provider）")
        if notes:
            md += "\n\n---\n" + " · ".join(notes)
        return ActionResult(
            self.id, ok=True, text=md, markdown=md,
            data={**ocr.data, "mode": "rules"},
            elapsed_ms=ocr.elapsed_ms,
        )

    def _rule_analysis(self, text: str) -> str:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        sections: list[tuple[str, str]] = []

        error_type, message = None, None
        # 真实 OCR 常把多行 traceback 合并成一行，所以在行内 search 而非整行 match
        is_traceback = any("traceback" in l.lower() for l in lines)
        if is_traceback:
            for l in reversed(lines):
                m = _PY_LAST_LINE.search(l)
                if m:
                    error_type, message = m.group(1), m.group(2).strip()
                    break

        if is_traceback and error_type:
            what = f"Python 抛出了 **{error_type}**"
            if message:
                what += f"：{message}"
            sections.append(("发生了什么", what))
            hint = _KNOWN_ERRORS.get(error_type)
            causes = []
            if hint:
                causes.append(hint + "。")
            if _CUDA_OOM.search(text):
                causes.append(
                    "GPU 显存不足：batch size 过大、模型/中间张量过大，或存在显存碎片。"
                )
            if error_type == "ModuleNotFoundError" and message:
                mod = message.split("'")[1] if "'" in message else None
                if mod:
                    causes.append(f"检查是否安装了 `{mod}`（pip install），以及是否在正确的虚拟环境中运行。")
            if not causes:
                causes.append(f"属于 {error_type} 的典型场景，请结合报错位置的代码检查输入/状态。")
            sections.append(("可能原因", "\n".join(f"- {c}" for c in causes)))
            file_hint = next((l for l in lines if 'File "' in l or '文件 "' in l), None)
            advice = ["查看 traceback 最上层的 `File \"...\", line N` 定位出错代码行。"]
            if file_hint:
                advice.insert(0, f"出错位置：`{file_hint.strip()}`")
            if _CUDA_OOM.search(text):
                advice.append("尝试减小 batch size；用 `torch.cuda.empty_cache()` 排除碎片；检查是否有张量意外驻留显存。")
            sections.append(("建议检查方向", "\n".join(f"- {a}" for a in advice)))
        else:
            # 通用错误线索：error/fatal/failed 等关键词行
            keys = [
                l for l in lines
                if re.search(r"\b(error|fatal|failed|failure|exception|denied|refused|timed? ?out)\b",
                             l, re.IGNORECASE)
            ]
            if keys:
                sections.append(("发生了什么", "识别内容中包含以下错误信息："))
                sections.append(("关键错误", "\n".join(f"- `{k}`" for k in keys[:5])))
                sections.append(("建议检查方向",
                                 "- 将关键错误行作为关键词在项目文档/搜索引擎中检索\n"
                                 "- 确认上下文（命令参数、路径、网络、权限）是否符合预期"))
            else:
                sections.append(("发生了什么", "未检测到明确的错误模式（Traceback / error / fatal 等）。"))
                sections.append(("建议检查方向",
                                 "- 如果这是报错，尝试框选完整错误信息（包含 Traceback 首行到最后一行）"))
        return "\n\n".join(f"**{t}**\n\n{body}" for t, body in sections)
