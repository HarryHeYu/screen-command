"""Windows.Media.Ocr provider —— 系统内置 OCR，完全本地、免费、零安装。

图片以内存字节 → InMemoryRandomAccessStream → BitmapDecoder → SoftwareBitmap
传入引擎，全程无临时文件。

后处理：zh 引擎会在每个汉字之间插入空格、使用全角标点，
`tidy_cjk_text` 做无损规整（不去除 CJK 与拉丁词之间的正常空格）。
"""

from __future__ import annotations

import asyncio
import re

from ..logutil import Timer, get_logger
from .base import OcrError, OcrResult, OCRProvider

log = get_logger()

# 中文引擎同时覆盖拉丁字母，且系统已确认安装 zh-Hans-CN / en-US 语言包。
DEFAULT_LANG_FALLBACK = ["zh-Hans-CN", "en-US"]

# 全角标点（中文标点区 + 全角符号区）
_FW_PUNCT = "\u3000-\u303f\uff01-\uff20\uff3b-\uff40\uff5b-\uff65"
_CJK_IDEO = "\u4e00-\u9fff"
_SPACE_BEFORE_PUNCT = re.compile(rf"\s+(?=[{_FW_PUNCT}])")
_SPACE_AFTER_PUNCT = re.compile(rf"(?<=[{_FW_PUNCT}])\s+")
_SPACE_BETWEEN_IDEO = re.compile(rf"(?<=[{_CJK_IDEO}])[ \t]+(?=[{_CJK_IDEO}])")
# 全角 ASCII 变体（！＂＃…～）→ 半角
_FW_TO_ASCII = {0xFF01 + i: 0x21 + i for i in range(0x5E)}


def tidy_cjk_text(text: str) -> str:
    """规整 Windows 中文 OCR 的空格与全角标点输出。"""
    text = _SPACE_BEFORE_PUNCT.sub("", text)
    text = _SPACE_AFTER_PUNCT.sub("", text)
    text = _SPACE_BETWEEN_IDEO.sub("", text)
    return text.translate(_FW_TO_ASCII)


def _lines_with_indent(ocr) -> list[str]:
    """用 word bounding box 重建行首缩进。

    Windows OCR 返回的行文本会剥离前导空格，代码/缩进文本因此丢失结构。
    引擎另提供每个词的矩形坐标：以整块文本的最左词为基准，
    用中位字符宽度估算每行的缩进空格数。任何异常都回退为原始行文本。
    """
    try:
        rows: list[tuple[list, int] | None] = []
        widths: list[float] = []
        min_left: int | None = None
        for line in ocr.lines:
            words = list(line.words)
            if not words:
                rows.append(None)
                continue
            x0 = words[0].bounding_rect.X
            rows.append((words, x0))
            if min_left is None or x0 < min_left:
                min_left = x0
            for w in words:
                if w.text and w.bounding_rect.Width > 0:
                    widths.append(w.bounding_rect.Width / len(w.text))
        if min_left is None:
            return [line.text for line in ocr.lines]
        widths.sort()
        char_w = widths[len(widths) // 2] if widths else 0.0
        if char_w <= 0:
            return [line.text for line in ocr.lines]
        out = []
        for row in rows:
            if row is None:
                out.append("")
                continue
            words, x0 = row
            indent = max(0, round((x0 - min_left) / char_w))
            out.append(" " * indent + " ".join(w.text for w in words))
        return out
    except Exception:  # noqa: BLE001 — 坐标重建失败不影响文本输出
        return [line.text for line in ocr.lines]


class WindowsOcrProvider(OCRProvider):
    """线程模型假设：OcrEngine 等 WinRT 对象默认 agile（可跨 apartment 使用），
    本 provider 的实例方法会在 QThreadPool worker 线程中被调用，每次调用
    各自 asyncio.run 独立事件循环。若未来出现 COM apartment 错误，
    优先怀疑多线程共享引擎 —— 届时改为 per-call 创建引擎。
    """

    name = "windows-media-ocr"

    def __init__(self, language: str | None = None) -> None:
        self._preferred = language
        self._engines: dict[str, object] = {}

    # -- availability ------------------------------------------------------

    def is_available(self) -> bool:
        try:
            return self._default_engine() is not None
        except Exception:  # noqa: BLE001
            return False

    @property
    def languages(self) -> list[str]:
        try:
            from winrt.windows.media.ocr import OcrEngine

            return [l.language_tag for l in OcrEngine.available_recognizer_languages]
        except Exception:  # noqa: BLE001
            return []

    # -- engine selection --------------------------------------------------

    def _default_engine(self):
        from winrt.windows.media.ocr import OcrEngine

        return OcrEngine.try_create_from_user_profile_languages()

    def _engine_for(self, language: str | None):
        from winrt.windows.globalization import Language
        from winrt.windows.media.ocr import OcrEngine

        if language:
            if language not in self._engines:
                eng = OcrEngine.try_create_from_language(Language(language))
                if eng is None:
                    raise OcrError(
                        f"OCR language pack not installed: {language} "
                        f"(available: {', '.join(self.languages)})"
                    )
                self._engines[language] = eng
            return self._engines[language]

        for tag in DEFAULT_LANG_FALLBACK:
            if tag in self._engines:
                return self._engines[tag]
            eng = OcrEngine.try_create_from_language(Language(tag))
            if eng is not None:
                self._engines[tag] = eng
                return eng
        return self._default_engine()

    # -- recognition -------------------------------------------------------

    def recognize(self, image_png: bytes, language: str | None = None) -> OcrResult:
        try:
            with Timer() as t:
                # 超时保护：WinRT recognize_async 万一挂起，不能让 worker 线程
                # 卡死到进程无法退出
                text, lines, lang, w, h = asyncio.run(
                    asyncio.wait_for(
                        self._recognize_async(image_png, language), timeout=15.0
                    )
                )
            text = tidy_cjk_text(text)
            lines = [tidy_cjk_text(l) for l in lines]
        except TimeoutError as exc:
            raise OcrError("Windows OCR timed out after 15s") from exc
        except OcrError:
            raise
        except Exception as exc:  # noqa: BLE001 — 统一转为领域错误
            raise OcrError(f"Windows OCR failed: {exc}") from exc
        log.info("ocr: windows-media-ocr done in %.1f ms (%d chars)", t.ms, len(text))
        return OcrResult(
            text=text,
            lines=lines,
            language=lang,
            provider=self.name,
            width_px=w,
            height_px=h,
            elapsed_ms=t.ms,
        )

    async def _recognize_async(self, image_png: bytes, language: str | None):
        from winrt.windows.globalization import Language
        from winrt.windows.graphics.imaging import (
            BitmapDecoder,
            BitmapPixelFormat,
            SoftwareBitmap,
        )
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

        engine = self._engine_for(language)
        assert isinstance(engine, OcrEngine)

        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream)
        writer.write_bytes(image_png)
        await writer.store_async()
        await writer.flush_async()
        stream.seek(0)

        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        if bitmap.bitmap_pixel_format != BitmapPixelFormat.BGRA8:
            bitmap = SoftwareBitmap.convert(bitmap, BitmapPixelFormat.BGRA8)

        ocr = await engine.recognize_async(bitmap)
        lang = engine.recognizer_language.language_tag
        if self._preferred:
            lang = f"{lang} (requested {self._preferred})"
        lines = _lines_with_indent(ocr)
        return ocr.text, lines, lang, bitmap.pixel_width, bitmap.pixel_height
