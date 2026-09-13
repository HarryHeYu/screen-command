"""开发状态窗口：替代系统托盘的最小控制面板（Capture 按钮 / 热键状态 / 退出）。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class StatusWindow(QWidget):
    capture_requested = Signal()
    cancel_requested = Signal()
    quit_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Screen Command (dev)")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(300, 170)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self._status = QLabel(
            "就绪 — Ctrl+Shift+A 框选菜单，Ctrl+Shift+1 快速 OCR 复制"
        )
        self._status.setWordWrap(True)
        btn = QPushButton("Capture (Ctrl+Shift+A)")
        btn.clicked.connect(self.capture_requested.emit)
        self._cancel_btn = QPushButton("取消当前动作")
        self._cancel_btn.clicked.connect(self.cancel_requested.emit)
        self._cancel_btn.setVisible(False)  # 仅执行动作期间可见
        quit_btn = QPushButton("退出")
        quit_btn.clicked.connect(self.quit_requested.emit)

        layout.addWidget(self._status)
        layout.addWidget(btn)
        layout.addWidget(self._cancel_btn)
        layout.addWidget(quit_btn)
        layout.addStretch(1)

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def set_processing(self, processing: bool) -> None:
        """执行动作期间显示取消入口（异步任务必须可取消，产品定义第 49 节）。"""
        self._cancel_btn.setVisible(processing)

    def set_hotkey_ok(self, ok: bool) -> None:
        if ok:
            self._status.setText(
                "热键已就绪 — Ctrl+Shift+A 框选菜单，Ctrl+Shift+1 快速 OCR 复制"
            )
        else:
            self._status.setText(
                "热键注册失败（可能被其他程序占用）— 请使用 Capture 按钮"
            )
