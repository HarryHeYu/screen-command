"""v0.1 的三个动作：OCR、Copy Text（OCR→剪贴板）、Save Image。"""

from __future__ import annotations

from ..logutil import Timer, get_logger
from ..ocr.base import OcrError, OCRProvider
from .base import Action, ActionContext, ActionResult

log = get_logger()


class OCRAction(Action):
    id = "ocr"
    name = "识别文字 (OCR)"
    hint = "English / 中文"
    shortcut = "1"

    def __init__(self, provider: OCRProvider) -> None:
        self.provider = provider

    def execute(self, ctx: ActionContext) -> ActionResult:
        if not ctx.image_png:
            return ActionResult(self.id, ok=False, error="no image captured")
        try:
            with Timer() as t:
                r = self.provider.recognize(ctx.image_png)
            if not r.text.strip():
                # 空结果要有用户可见反馈，不能显示一个空窗口让人以为坏了
                return ActionResult(
                    self.id,
                    ok=False,
                    error="未识别到文字 —— 选区内可能没有文本，或文字太小/对比度太低。可尝试框选更大的区域后重试。",
                    data={"provider": r.provider},
                    elapsed_ms=t.ms,
                )
            return ActionResult(
                self.id,
                ok=True,
                text=r.text,
                data={
                    "provider": r.provider,
                    "language": r.language,
                    "width_px": r.width_px,
                    "height_px": r.height_px,
                    "lines": r.lines,  # 供 Code/Markdown 等下游动作使用
                },
                elapsed_ms=t.ms,
            )
        except OcrError as exc:
            log.error("action %s: %s", self.id, exc)
            return ActionResult(self.id, ok=False, error=str(exc))
        except Exception as exc:  # noqa: BLE001 — action 不向 UI 抛异常
            log.exception("action %s: unexpected failure", self.id)
            return ActionResult(self.id, ok=False, error=f"unexpected: {exc}")


class CopyTextAction(Action):
    """OCR → 复制到剪贴板。

    线程约束：QClipboard 只能在 GUI 主线程使用。execute 只产出
    `data["copy_to_clipboard"]` 意图标记，由 AppController 在主线程写入剪贴板。
    """

    id = "copy_text"
    name = "复制文字"
    hint = "OCR 并复制到剪贴板"
    shortcut = "2"

    def __init__(self, provider: OCRProvider) -> None:
        self.provider = provider
        self._ocr = OCRAction(provider)

    def execute(self, ctx: ActionContext) -> ActionResult:
        ocr_result = self._ocr.execute(ctx)
        if not ocr_result.ok:
            return ocr_result
        out = dict(ocr_result.data)
        out["copy_to_clipboard"] = True
        return ActionResult(self.id, ok=True, text=ocr_result.text, data=out,
                            elapsed_ms=ocr_result.elapsed_ms)


class SaveImageAction(Action):
    """把框选区域保存为 PNG。显式动作才写文件（不默认保存每次截图）。

    线程约束：QFileDialog 只能在 GUI 主线程弹出 —— 路径选择由 AppController
    在派发本动作前完成并写入 ctx.options["output_path"]。
    """

    id = "save_image"
    name = "保存截图"
    hint = "PNG"
    shortcut = "7"
    needs_image = True

    def execute(self, ctx: ActionContext) -> ActionResult:
        if not ctx.image_png:
            return ActionResult(self.id, ok=False, error="no image captured")
        path = ctx.options.get("output_path")
        if not path:
            return ActionResult(self.id, ok=False, error="no output path (cancelled?)")
        try:
            with open(path, "wb") as f:
                f.write(ctx.image_png)
        except OSError as exc:
            return ActionResult(self.id, ok=False, error=f"save failed: {exc}")
        return ActionResult(self.id, ok=True, text=str(path), data={"path": str(path)})
