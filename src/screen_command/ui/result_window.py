"""Result Window：动作结果展示（可选中 / 复制 / 编辑 / 重试 / 换动作 / 关闭）。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..actions.base import ActionResult

WIN_STYLE = """
QWidget#ResultWindow { background: #1b1e24; }
QLabel#rTitle { color: #e8e8ea; font-size: 14px; font-weight: bold; }
QLabel#rMeta { color: #9aa0a8; font-size: 11px; }
QTextEdit#rText {
    background: #23262d; color: #e8e8ea; border: 1px solid #33383f;
    border-radius: 6px; padding: 8px; font-size: 13px; selection-background-color: #2d5a8c;
}
QPushButton#rBtn {
    background: #2c3038; color: #e8e8ea; border: none; border-radius: 6px;
    padding: 6px 16px; font-size: 12px;
}
QPushButton#rBtn:hover { background: #3a4048; }
QPushButton#rPrimary { background: #0e6d8c; }
QPushButton#rPrimary:hover { background: #1284a8; }
"""


class ResultWindow(QWidget):
    retry_requested = Signal()
    rerun_requested = Signal()
    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ResultWindow")
        self.setStyleSheet(WIN_STYLE)
        self.setWindowFlags(Qt.WindowType.Window)
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        self._title = QLabel("结果")
        self._title.setObjectName("rTitle")
        self._meta = QLabel("")
        self._meta.setObjectName("rMeta")

        self._text = QTextEdit()
        self._text.setObjectName("rText")
        self._text.setReadOnly(True)
        self._text.setAcceptRichText(False)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self._text.setFont(mono)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        self._btn_copy = QPushButton("复制")
        self._btn_copy.setObjectName("rBtn rPrimary")
        self._btn_edit = QPushButton("编辑")
        self._btn_edit.setObjectName("rBtn")
        self._btn_retry = QPushButton("重试")
        self._btn_retry.setObjectName("rBtn")
        self._btn_another = QPushButton("其他动作")
        self._btn_another.setObjectName("rBtn")
        self._btn_close = QPushButton("关闭")
        self._btn_close.setObjectName("rBtn")

        self._btn_copy.clicked.connect(self._copy)
        self._btn_edit.clicked.connect(self._toggle_edit)
        self._btn_retry.clicked.connect(self.retry_requested.emit)
        self._btn_another.clicked.connect(self.rerun_requested.emit)
        self._btn_close.clicked.connect(self.close)

        for b in (self._btn_copy, self._btn_edit, self._btn_retry,
                  self._btn_another, self._btn_close):
            btns.addWidget(b)
        btns.addStretch(1)

        layout.addWidget(self._title)
        layout.addWidget(self._meta)
        layout.addWidget(self._text, 1)
        layout.addLayout(btns)

        self._last_result: ActionResult | None = None

    def show_result(self, result: ActionResult) -> None:
        self._last_result = result
        self._title.setText("结果 — 识别成功" if result.ok else "结果 — 失败")
        if result.ok:
            self._text.setPlainText(result.text)
            meta = [f"{result.data.get('provider', '')}".strip(),
                    f"{result.elapsed_ms:.0f} ms"]
            lang = result.data.get("language")
            if lang:
                meta.insert(1, str(lang))
            size = result.data.get("width_px")
            if size:
                meta.insert(2, f"{size}×{result.data.get('height_px')} px")
            if result.data.get("copied"):
                meta.append("已复制到剪贴板")
            self._meta.setText(" · ".join(m for m in meta if m))
        else:
            self._text.setPlainText(f"动作执行失败：\n\n{result.error}")
            self._meta.setText(result.action_id)
        # 失败结果没有可复制的产出 —— 避免把错误文案复制走
        self._btn_copy.setEnabled(result.ok)
        self._text.setReadOnly(True)
        self._btn_edit.setText("编辑")
        self.show()
        self.raise_()
        self.activateWindow()

    def _copy(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self._text.toPlainText())

    def _toggle_edit(self) -> None:
        ro = self._text.isReadOnly()
        self._text.setReadOnly(not ro)
        self._btn_edit.setText("锁定" if not ro else "编辑")

    def keyPressEvent(self, ev) -> None:
        if ev.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(ev)

    def closeEvent(self, ev) -> None:
        self.closed.emit()
        super().closeEvent(ev)
