"""Capture Core 测试：DPI 换算 / 边缘夹取（不依赖真实屏幕内容）。"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPixmap

from screen_command.capture import crop_snapshot, pixmap_to_png_bytes, ScreenSnapshot


class FakeScreen:
    """QScreen 替身：geometry() 为方法（与 QScreen 一致）。"""

    def __init__(self, x: int, y: int, w: int, h: int, name: str = "fake") -> None:
        self._geo = QRect(x, y, w, h)
        self._name = name

    def geometry(self) -> QRect:
        return self._geo

    def name(self) -> str:
        return self._name


def make_snapshot(x, y, w, h, dpr, name="fake") -> ScreenSnapshot:
    """纯色可定位快照：像素 (px, py) 颜色编码其物理坐标（r=px%256, g=py%256）。"""
    img = QPixmap(round(w * dpr), round(h * dpr))
    img.fill(QColor(0, 0, 0))
    p = QPainter(img)
    for px in range(0, img.width(), max(1, img.width() // 16)):
        p.setPen(QColor(px % 256, 0, 0))
        p.drawLine(px, 0, px, img.height())
    for py in range(0, img.height(), max(1, img.height() // 16)):
        p.setPen(QColor(0, py % 256, 0))
        p.drawLine(0, py, img.width(), py)
    p.end()
    img.setDevicePixelRatio(dpr)
    return ScreenSnapshot(screen=FakeScreen(x, y, w, h, name), pixmap=img)  # type: ignore[arg-type]


@pytest.mark.usefixtures("qapp")
class TestCrop:
    def test_dpr2_crop_size(self):
        snap = make_snapshot(0, 0, 200, 100, dpr=2.0)
        pm = crop_snapshot(snap, QRect(10, 10, 50, 25))
        assert pm.width() == 100 and pm.height() == 50  # 物理像素
        assert pm.devicePixelRatio() == 2.0

    def test_dpr1_identity(self):
        snap = make_snapshot(0, 0, 100, 100, dpr=1.0)
        pm = crop_snapshot(snap, QRect(0, 0, 100, 100))
        assert pm.width() == 100 and pm.height() == 100

    def test_secondary_screen_offset(self):
        # 副屏位于负坐标（本机真实拓扑：-2048）
        snap = make_snapshot(-2048, 0, 800, 600, dpr=1.0, name="left")
        pm = crop_snapshot(snap, QRect(-2048, 100, 200, 50))
        assert pm.width() == 200 and pm.height() == 50

    def test_screen_edge_clamp(self):
        # 选区越出屏幕右/下边缘 → 夹取到屏幕内
        snap = make_snapshot(0, 0, 200, 100, dpr=1.0)
        pm = crop_snapshot(snap, QRect(150, 80, 200, 100))
        assert pm.width() == 50 and pm.height() == 20

    def test_region_outside_screen_entirely(self):
        snap = make_snapshot(0, 0, 200, 100, dpr=1.0)
        pm = crop_snapshot(snap, QRect(500, 500, 50, 50))
        assert pm.isNull() or (pm.width() == 0)

    def test_png_bytes_roundtrip(self):
        snap = make_snapshot(0, 0, 40, 40, dpr=1.0)
        data = pixmap_to_png_bytes(crop_snapshot(snap, QRect(0, 0, 40, 40)))
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(data) > 100
