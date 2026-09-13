"""Action 层入口：注册表 + 内置动作。"""

from __future__ import annotations

from .base import (
    Action,
    ActionContext,
    ActionResult,
    all_actions,
    clear_actions,
    get_action,
    register_action,
)
from .builtin import CopyTextAction, OCRAction, SaveImageAction
from .v02 import CodeOCRAction, ExplainErrorAction, MarkdownAction, TranslateAction

__all__ = [
    "Action",
    "ActionContext",
    "ActionResult",
    "all_actions",
    "clear_actions",
    "get_action",
    "register_action",
    "OCRAction",
    "CopyTextAction",
    "SaveImageAction",
    "TranslateAction",
    "CodeOCRAction",
    "MarkdownAction",
    "ExplainErrorAction",
]

# 动作 id → 构造方式（provider 注入需求不同）
PROVIDER_BASED = {"ocr", "copy_text", "translate", "code", "markdown", "explain"}


def build_default_actions(
    ocr_provider,
    translation_provider=None,
    llm_provider=None,
) -> list[Action]:
    """构造 v0.2 默认动作集（菜单顺序即快捷键顺序），并写入注册表。"""
    actions = [
        OCRAction(ocr_provider),
        CopyTextAction(ocr_provider),
        TranslateAction(ocr_provider, translation_provider),
        CodeOCRAction(ocr_provider),
        MarkdownAction(ocr_provider),
        ExplainErrorAction(ocr_provider, llm_provider),
        SaveImageAction(),
    ]
    for a in actions:
        register_action(a)
    return actions


def build_action_by_id(action_id: str, ocr_provider, translation_provider=None,
                       llm_provider=None) -> Action:
    """CLI harness 用：按 id 构造单个动作。"""
    if action_id == "save_image":
        return SaveImageAction()
    makers = {
        "ocr": lambda: OCRAction(ocr_provider),
        "copy_text": lambda: CopyTextAction(ocr_provider),
        "translate": lambda: TranslateAction(ocr_provider, translation_provider),
        "code": lambda: CodeOCRAction(ocr_provider),
        "markdown": lambda: MarkdownAction(ocr_provider),
        "explain": lambda: ExplainErrorAction(ocr_provider, llm_provider),
    }
    if action_id not in makers:
        raise KeyError(f"unknown action: {action_id!r}")
    return makers[action_id]()
