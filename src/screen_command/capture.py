"""Capture Core：屏幕快照与区域裁剪。

设计要点（见 docs/DECISIONS.md D3）：
- 触发框选前先对每块屏幕抓一张全屏快照（QScreen.grabWindow），
  overlay 以这张冻结快照为背景，保证截图永不包含 overlay 自身。
- 选区以「全局逻辑坐标」表示；裁剪时按目标屏 devicePixelRatio 换算物理像素。
- 全程内存（QPixmap / PNG bytes），除显式 Save 动作外不落盘。
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QBuffer, QByteArray, QRect
from PySide6.QtGui import QGuiApplication, QPixmap, QScreen

from .logutil import Timer, get_logger

log = get_logger()


@dataclass
class ScreenSnapshot:
    """单块屏幕的冻结快照。pixmap 的 size() 是逻辑像素，devicePixelRatio 为缩放比。"""

    screen: QScreen
    pixmap: QPixmap

    @property
    def geometry(self) -> QRect:
        return self.screen.geometry()

    @property
    def dpr(self) -> float:
        return self.pixmap.devicePixelRatio() or 1.0


def snapshot_all_screens() -> list[ScreenSnapshot]:
    """抓取所有屏幕的全屏快照。"""
    snaps: list[ScreenSnapshot] = []
    with Timer() as t:
        for screen in QGuiApplication.screens():
            pm = screen.grabWindow(0)
            snaps.append(ScreenSnapshot(screen=screen, pixmap=pm))
    log.info("capture: %d screen(s) snapshot in %.1f ms", len(snaps), t.ms)
    return snaps


def screen_for_global_point(x: float, y: float) -> QScreen:
    """返回包含该全局逻辑坐标点的屏幕。"""
    for screen in QGuiApplication.screens():
        if screen.geometry().contains(int(x), int(y)):
            return screen
    return QGuiApplication.primaryScreen()


def crop_snapshot(snapshot: ScreenSnapshot, global_logical_rect: QRect) -> QPixmap:
    """从快照中按全局逻辑坐标矩形裁剪，返回物理分辨率的 QPixmap。

    自动夹取到屏幕范围以内（屏幕边缘 / 越界拖拽的容错）。
    """
    geo = snapshot.geometry
    dpr = snapshot.dpr
    local = global_logical_rect.translated(-geo.topLeft())
    phys = QRect(
        round(local.x() * dpr),
        round(local.y() * dpr),
        round(local.width() * dpr),
        round(local.height() * dpr),
    ).intersected(QRect(0, 0, snapshot.pixmap.width(), snapshot.pixmap.height()))
    if phys.isEmpty():
        # 选区与屏幕完全不相交（异常坐标 / 全程在屏外拖拽）→ 返回空图而非整屏
        return QPixmap()
    pm = snapshot.pixmap.copy(phys)
    pm.setDevicePixelRatio(dpr)
    return pm


def pixmap_to_png_bytes(pm: QPixmap) -> bytes:
    """QPixmap → PNG 字节流（内存操作，不落盘）。"""
    buf = QBuffer()
    buf.open(QBuffer.OpenModeFlag.ReadWrite)
    pm.save(buf, "PNG")
    data = bytes(buf.data())
    buf.close()
    return data
