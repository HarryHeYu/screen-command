"""运行配置（config.toml，缺省有内置默认值）。

热键默认选 Alt+W / Alt+X：单修饰键左手可及（微信 Alt+A 截图同款手感），
且经本机实测空闲——Ctrl+Shift+字母、Ctrl+Alt+字母 在装有输入法/音乐/游戏
外设软件的机器上极易撞车。被占用时在项目根目录建 config.toml 覆盖即可，
无需改代码。
不写注册表 / 用户目录，保持 project-local。
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.toml"

DEFAULT_CAPTURE_HOTKEY = "alt+w"
DEFAULT_QUICK_OCR_HOTKEY = "alt+x"


@dataclass
class HotkeyConfig:
    capture: str = DEFAULT_CAPTURE_HOTKEY
    quick_ocr: str = DEFAULT_QUICK_OCR_HOTKEY


def load_hotkeys(path: Path | None = None) -> HotkeyConfig:
    """读取 config.toml 的 [hotkey] 段（可缺省）。非法值回退默认并告警。"""
    from .hotkey import parse_combo

    cfg = HotkeyConfig()
    p = path or CONFIG_PATH
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
