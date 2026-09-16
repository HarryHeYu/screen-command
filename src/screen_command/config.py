"""运行配置（config.toml，缺省有内置默认值）。

热键默认选 Alt+W / Alt+X：单修饰键左手可及（微信 Alt+A 截图同款手感），
且经本机实测空闲——Ctrl+Shift+字母、Ctrl+Alt+字母 在装有输入法/音乐/游戏
外设软件的机器上极易撞车。被占用时在项目根目录建 config.toml 覆盖即可，
无需改代码。
不写注册表 / 用户目录，保持 project-local。
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CAPTURE_HOTKEY = "alt+w"
DEFAULT_QUICK_OCR_HOTKEY = "alt+x"


@dataclass
class HotkeyConfig:
    capture: str = DEFAULT_CAPTURE_HOTKEY
    quick_ocr: str = DEFAULT_QUICK_OCR_HOTKEY


def _repo_root() -> Path | None:
    """开发安装时定位仓库根（含 pyproject.toml 的目录）。

    本文件位于 ``<root>/src/screen_command/config.py``，所以 ``parents[2]``
    是仓库根；wheel 安装到 site-packages 时该路径无效，返回 None。
    """
    here = Path(__file__).resolve()
    try:
        root = here.parents[2]
    except IndexError:
        return None
    if (root / "pyproject.toml").is_file() or (root / "config.example.toml").is_file():
        return root
    return None


def resolve_config_path(explicit: Path | None = None) -> Path:
    """解析 config.toml 路径，不要求文件一定存在。

    优先级：显式参数 → ``SCREEN_COMMAND_CONFIG`` → 当前工作目录中已存在的
    ``config.toml`` → 仓库根 ``config.toml`` → 回退为 ``<cwd>/config.toml``。
    """
    if explicit is not None:
        return explicit
    env = os.environ.get("SCREEN_COMMAND_CONFIG")
    if env:
        return Path(env)
    cwd_cfg = Path.cwd() / "config.toml"
    if cwd_cfg.is_file():
        return cwd_cfg
    root = _repo_root()
    if root is not None:
        return root / "config.toml"
    return cwd_cfg


# 兼容旧引用：指向仓库根（或 cwd），不再误指向 src/
PROJECT_ROOT = _repo_root() or Path.cwd()
CONFIG_PATH = PROJECT_ROOT / "config.toml"


def load_hotkeys(path: Path | None = None) -> HotkeyConfig:
    """读取 config.toml 的 [hotkey] 段（可缺省）。非法值回退默认并告警。"""
    from .hotkey import parse_combo

    cfg = HotkeyConfig()
    p = resolve_config_path(path)
    if not p.exists():
        return cfg
    try:
        raw = tomllib.loads(p.read_text(encoding="utf-8")).get("hotkey", {})
    except (tomllib.TOMLDecodeError, OSError):
        import logging

        logging.getLogger("screen_command").warning(
            "config: failed to parse %s — using default hotkeys", p
        )
        return cfg
    for field in ("capture", "quick_ocr"):
        value = raw.get(field)
        if not value:
            continue
        try:
            parse_combo(str(value))
        except ValueError as exc:
            import logging

            logging.getLogger("screen_command").warning(
                "config: %s — keeping default %s", exc, getattr(cfg, field)
            )
            continue
        setattr(cfg, field, str(value).lower())
    return cfg
