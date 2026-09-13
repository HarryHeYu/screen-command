"""Action 抽象与注册表。

统一接口（对齐产品定义第 8 节）：

    Action
    ├─ id / name / hint / shortcut / needs_image
    └─ execute(ActionContext) -> ActionResult

ActionResult 是结构化结果（第 40 节），不允许 action 向 UI 塞裸字符串。
Action 不 import 任何 UI 模块；UI 通过注册表发现动作。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from PySide6.QtCore import QRect
from PySide6.QtGui import QImage

if TYPE_CHECKING:
    from ..ocr.base import OcrResult


@dataclass
class ActionContext:
    """一次动作执行的输入。image_png 是框选区域的物理分辨率 PNG 字节流。

    cancel_token: 协作式取消挂钩（threading.Event）。AppController 在每次执行
    动作前注入新事件，用户取消时置位；本地 OCR 不可中断，取消语义为丢弃结果；
    网络类 provider 应在分步执行时检查该事件。
    """

    image_png: bytes | None = None
    image: QImage | None = None
    region: QRect | None = None
    screen_label: str = ""
    options: dict = field(default_factory=dict)
    cancel_token: object | None = None


@dataclass
class ActionResult:
    action_id: str
    ok: bool
    text: str = ""
    markdown: str | None = None
    data: dict = field(default_factory=dict)
    error: str | None = None
    elapsed_ms: float = 0.0


class Action(ABC):
    id: str = "abstract"
    name: str = "Abstract"
    hint: str = ""  # 菜单里展示的简短说明
    shortcut: str = ""  # 菜单数字键提示，如 "1"
    needs_image: bool = True

    @abstractmethod
    def execute(self, ctx: ActionContext) -> ActionResult:
        """同步执行动作（调用方负责放到后台线程）。不应抛异常，失败封装进 ActionResult。"""


# ---------------------------------------------------------------- registry

_REGISTRY: "OrderedDict[str, Action]" = OrderedDict()


def register_action(action: Action) -> None:
    _REGISTRY[action.id] = action


def all_actions() -> list[Action]:
    return list(_REGISTRY.values())


def get_action(action_id: str) -> Action | None:
    return _REGISTRY.get(action_id)


def clear_actions() -> None:
    """主要供测试隔离使用。"""
    _REGISTRY.clear()
