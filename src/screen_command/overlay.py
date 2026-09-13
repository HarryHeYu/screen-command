"""Selection Overlay：每块屏幕一个全屏窗口，背景为冻结的屏幕快照 + 暗色蒙层。

- 拖拽出选区：选区内显示原始亮度，外部压暗；边框 + 物理像素尺寸提示。
- Esc 取消；点击（无拖动）/ 零尺寸选择视为取消。
- 选区以全局逻辑坐标上报，裁剪换算由 CaptureCore 负责。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from .capture import ScreenSnapshot

DIM_ALPHA = 110
BORDER_COLOR = QColor(0, 200, 255)
HINT_BG = QColor(20, 22, 26, 235)


class OverlayWindow(QWidget):
    finished = Signal(QRect)  # 全局逻辑坐标选区
    cancelled = Signal()

    def __init__(self, snapshot: ScreenSnapshot, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._snap = snapshot
        self._pm: QPixmap = snapshot.pixmap
        self._dpr = self._pm.devicePixelRatio() or 1.0
        self._origin: QPoint | None = None  # 本窗口（逻辑）坐标
        self._current: QPoint | None = None
        self._dragging = False

        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setGeometry(snapshot.geometry)

    # -- lifecycle ---------------------------------------------------------

    def open_overlay(self) -> None:
        self.showFullScreen()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    # -- events ------------------------------------------------------------

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self._origin = ev.position().toPoint()
            self._current = self._origin
            self._dragging = True
            self.update()

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:
        if self._dragging:
            self._current = ev.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, ev: QMouseEvent) -> None:
        if not self._dragging or ev.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging = False
        rect = self._selection_rect(ev.position().toPoint())
        if rect.width() < 2 or rect.height() < 2:
            # 点击 / 零尺寸选择 → 取消
            self.cancelled.emit()
            return
        self.finished.emit(self._to_global(rect))

    def keyPressEvent(self, ev) -> None:
        if ev.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            return
        super().keyPressEvent(ev)

    # -- geometry helpers --------------------------------------------------

    def _selection_rect(self, end: QPoint) -> QRect:
        assert self._origin is not None
        return QRect(self._origin, end).normalized()

    def _to_global(self, local_rect: QRect) -> QRect:
        return local_rect.translated(self._snap.geometry.topLeft())

    def _physical_size(self, rect: QRect) -> tuple[int, int]:
        return round(rect.width() * self._dpr), round(rect.height() * self._dpr)

    # -- painting ----------------------------------------------------------

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        # 背景：冻结快照（逻辑尺寸 1:1 铺满窗口）
        p.drawPixmap(self.rect(), self._pm)
        # 全屏暗色蒙层
        p.fillRect(self.rect(), QColor(0, 0, 0, DIM_ALPHA))

        if self._dragging and self._origin is not None and self._current is not None:
            rect = self._selection_rect(self._current)
            if rect.width() >= 1 and rect.height() >= 1:
                # 选区还原亮度：从快照重绘该区域（源/目标都需 QRectF，PySide6 不接受混用重载）
                src = QRectF(
                    rect.x() * self._dpr,
                    rect.y() * self._dpr,
                    rect.width() * self._dpr,
                    rect.height() * self._dpr,
                )
                p.drawPixmap(QRectF(rect), self._pm, src)
                # 边框
                pen = QPen(BORDER_COLOR)
                pen.setWidth(2)
                p.setPen(pen)
                p.drawRect(rect)
                # 尺寸提示
                w, h = self._physical_size(rect)
                self._draw_size_label(p, rect, f"{w} × {h} px")

    def _draw_size_label(self, p: QPainter, rect: QRect, text: str) -> None:
        font = QFont(self.font())
        font.setPointSize(10)
        p.setFont(font)
        metrics = p.fontMetrics()
        tw = metrics.horizontalAdvance(text) + 12
        th = metrics.height() + 6
        # 优先放选区上方，贴顶时放下方
        x = min(max(rect.x(), 4), self.width() - tw - 4)
        y = rect.y() - th - 6
        if y < 4:
            y = rect.y() + rect.height() + 6
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(HINT_BG)
        p.drawRoundedRect(x, y, tw, th, 4, 4)
        p.setPen(QPen(QColor(240, 240, 240)))
        p.drawText(x + 6, y + metrics.ascent() + 3, text)
