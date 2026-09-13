"""CLI 入口。

    screen_command run                       # GUI（热键 + Capture 按钮）
    screen_command process IMG --action ocr  # 测试 harness：对图片直接执行 action
    screen_command providers                 # 列出可用 OCR provider
"""

from __future__ import annotations

import argparse
import sys


def _cmd_run(args) -> int:
    from PySide6.QtWidgets import QApplication

    from .app import AppController

    app = QApplication(sys.argv)
    app.setApplicationName("Screen Command")
    controller = AppController()
    controller.run()
    return app.exec()


def _cmd_process(args) -> int:
    """脱离真实屏幕测试 action：读图片 → 执行 → 输出结果。"""
    from .actions import build_action_by_id
    from .actions.base import ActionContext
    from .ocr import make_provider
    from .providers import make_llm_provider, make_translation_provider

    try:
        with open(args.image, "rb") as f:
            image_png = f.read()
    except OSError as exc:
        print(f"error: cannot read image: {exc}", file=sys.stderr)
        return 2

    provider = make_provider(args.provider, language=args.language)
    try:
        action = build_action_by_id(
            args.action, provider,
            translation_provider=make_translation_provider(),
            llm_provider=make_llm_provider(),
        )
    except KeyError:
        print(f"error: unknown action {args.action!r}", file=sys.stderr)
        return 2

    ctx = ActionContext(image_png=image_png, options=dict(args.opt or []))
    result = action.execute(ctx)

    if not result.ok:
        print(f"error: {result.error}", file=sys.stderr)
        return 1
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result.text)
        print(f"saved → {args.output}")
    elif args.md and result.markdown:
        print(result.markdown)
    else:
        print(result.text)
    meta = result.data
    if meta:
        print(
            f"[{result.action_id} · {meta.get('provider', '')} · "
            f"{meta.get('language', '')} · {result.elapsed_ms:.0f} ms]",
            file=sys.stderr,
        )
    return 0


def _cmd_providers(_args) -> int:
    from .ocr import make_provider

    for name in ("windows", "mock"):
        try:
            p = make_provider(name)
            print(f"{name:12} available={p.is_available()}  languages={p.languages}")
        except Exception as exc:  # noqa: BLE001
            print(f"{name:12} unavailable ({exc})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="screen_command",
        description="框选屏幕区域 → 识别内容 → 直接执行动作。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="启动 GUI（热键框选，默认 Alt+W）")
    p_run.set_defaults(func=_cmd_run)

    p_cap = sub.add_parser("capture", help="同 run（GUI 一次框选流程）")
    p_cap.set_defaults(func=_cmd_run)

    p_proc = sub.add_parser("process", help="对图片执行 action（测试 harness）")
    p_proc.add_argument("image", help="PNG/JPEG 图片路径")
    p_proc.add_argument("--action", default="ocr",
                        help="ocr | copy_text | translate | code | markdown | explain | save_image")
    p_proc.add_argument("--provider", default="auto", help="auto | windows | mock")
    p_proc.add_argument("--language", default=None, help="BCP-47，如 zh-Hans-CN")
    p_proc.add_argument("--output", default=None, help="结果写入文件")
    p_proc.add_argument("--md", action="store_true",
                        help="结果有 markdown 视图时（code/markdown）输出 markdown")
    p_proc.add_argument("--opt", action="append", nargs=2, metavar=("KEY", "VALUE"),
                        help="传给 action 的选项，如 --opt output_path out.png")
    p_proc.set_defaults(func=_cmd_process)

    p_prov = sub.add_parser("providers", help="列出可用 OCR provider")
    p_prov.set_defaults(func=_cmd_providers)

    args = parser.parse_args(argv)
    if hasattr(args, "opt") and args.opt:
        args.opt = {k: v for k, v in args.opt}
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
