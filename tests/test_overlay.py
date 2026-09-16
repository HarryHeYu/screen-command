"""Overlay 交互：右键取消（不依赖真实屏幕内容）。"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from screen_command.overlay import OverlayWindow
from tests.test_capture import make_snapshot


@pytest.mark.usefixtures("qapp")
def test_right_click_cancels():
    snap = make_snapshot(0, 0, 120, 80, dpr=1.0)
    ov = OverlayWindow(snap)
    cancelled: list[bool] = []
    ov.cancelled.connect(lambda: cancelled.append(True))
    QTest.mouseClick(ov, Qt.MouseButton.RightButton)
    assert cancelled
    ov.close()
