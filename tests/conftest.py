"""pytest 共享夹具：确保测试图片存在、提供 mock provider 与 QApplication。"""

from __future__ import annotations

import pytest

from tests.make_fixtures import ensure_fixtures


@pytest.fixture(scope="session", autouse=True)
def fixtures() -> dict:
    return ensure_fixtures()


@pytest.fixture(scope="session")
def qapp():
    """QGuiApplication 实例（offscreen 不可用时用真实平台）。"""
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([])
    yield app
