"""Action Menu：框选结束后弹出的小浮窗，键盘数字键可直接触发动作。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..actions.base import Action

ACCENT = "#00c8ff"
BTN_STYLE = f"""
QPushButton {{
    text-align: left; padding: 7px 14px; border: none; border-radius: 6px;
    background: transparent; color: #e8e8ea; font-size: 13px;
}}
QPushButton:hover {{ background: #2c3038; }}
QPushButton:pressed {{ background: #3a4048; }}
"""

MENU_STYLE = f"""
QWidget#ActionMenu {{
    background: #1b1e24; border: 1px solid #33383f; border-radius: 8px;
}}
QLabel#menuTitle {{ color: #9aa0a8; font-size: 11px; padding: 8px 14px 2px 14px; }}
QLabel#shortcut {{ color: {ACCENT}; font-weight: bold; }}
"""


class ActionMenu(QFrame):
    action_selected = Signal(object)  # Action
    cancelled = Signal()

    def __init__(self, actions: list[Action], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ActionMenu")
        self.setStyleSheet(MENU_STYLE)
        self.setWindowFlags(
            Qt.WindowType.Popup  # 点击外部自动关闭 → 取消
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 8)
        layout.setSpacing(2)

        title = QLabel("选择动作")
        title.setObjectName("menuTitle")
        layout.addWidget(title)

        self._by_key: dict[str, Action] = {}
        self._picked = False  # 区分「用户选择了动作」与「Esc/点击外部取消」
        for i, action in enumerate(actions):
            key = action.shortcut or str((i + 1) % 10)
            self._by_key[key] = action
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(8, 0, 8, 0)
            h.setSpacing(10)
            key_label = QLabel(key)
            key_label.setObjectName("shortcut")
            btn = QPushButton(f"{action.name}   {action.hint}".strip())
            btn.setStyleSheet(BTN_STYLE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, a=action: self._pick(a))
            h.addWidget(key_label)
            h.addWidget(btn, 1)
            layout.addWidget(row)

        tip = QLabel("Esc 取消 · 数字键快速选择")
        tip.setObjectName("menuTitle")
        layout.addWidget(tip)

    def _pick(self, action: Action) -> None:
        self._picked = True
        self.close()
        self.action_selected.emit(action)

    def hideEvent(self, ev) -> None:
        # Qt.Popup 被点击外部/系统关闭时不会走 keyPressEvent —— 在这里统一补发取消，
        # 否则 AppController 会卡在 CHOOSING 状态。
        if not self._picked:
            self._picked = True
            self.cancelled.emit()
        super().hideEvent(ev)

    def keyPressEvent(self, ev) -> None:
        text = ev.text()
        if ev.key() == Qt.Key.Key_Escape:
            self.close()  # hideEvent 会发出 cancelled
            return
        if text in self._by_key:
            self._pick(self._by_key[text])
            return
        super().keyPressEvent(ev)

    def popup_at(self, x: int, y: int, screen_rect) -> None:
        """在指定点弹出，自动收进屏幕范围内。"""
        self.adjustSize()
        w, h = self.width(), self.height()
        x = min(max(4, x), screen_rect.right() - w - 4)
        y = min(max(4, y), screen_rect.bottom() - h - 4)
        self.move(x, y)
        self.show()
        self.setFocus(Qt.FocusReason.PopupFocusReason)
