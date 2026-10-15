"""版本一致性：包内 __version__ 必须与 pyproject.toml 保持一致。"""

from __future__ import annotations

import tomllib
from pathlib import Path

from screen_command import __version__


def test_package_version_matches_pyproject():
    root = Path(__file__).resolve().parents[1]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["version"] == __version__
