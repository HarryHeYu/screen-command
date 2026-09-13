"""pytest 共享夹具：确保测试图片存在、提供 mock provider 与 QApplication。"""

from __future__ import annotations

import pytest

from tests.make_fixtures import ensure_fixtures


@pytest.fixture(scope="session", autouse=True)
def fixtures() -> dict:
    return ensure_fixtures()


@pytest.fixture(scope="session")
def qapp():
    """QApplication 实例（widget 需要；测试不 show 窗口）。"""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
