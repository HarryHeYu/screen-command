"""热键解析与配置加载测试（不注册真实系统热键）。"""

from __future__ import annotations

import pytest

from screen_command.config import DEFAULT_CAPTURE_HOTKEY, DEFAULT_QUICK_OCR_HOTKEY, load_hotkeys
from screen_command.hotkey import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    parse_combo,
)


class TestParseCombo:
    def test_ctrl_alt_q(self):
        mods, vk = parse_combo("ctrl+alt+q")
        assert mods == MOD_CONTROL | MOD_ALT | MOD_NOREPEAT
        assert vk == ord("Q")

    def test_case_insensitive(self):
        assert parse_combo("Ctrl+Alt+W") == parse_combo("ctrl+alt+w")

    def test_two_modifiers(self):
        from screen_command.hotkey import MOD_SHIFT

        mods, vk = parse_combo("ctrl+shift+q")
        assert mods == MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT
        assert vk == ord("Q")

    def test_three_modifiers_raises(self):
        with pytest.raises(ValueError):
            parse_combo("ctrl+shift+alt+q")

    def test_digit_key(self):
        mods, vk = parse_combo("ctrl+alt+1")
        assert vk == ord("1")

    def test_missing_modifier_raises(self):
        with pytest.raises(ValueError):
            parse_combo("q")

    def test_unknown_modifier_raises(self):
        with pytest.raises(ValueError):
            parse_combo("hyper+q")

    def test_non_alnum_key_raises(self):
        with pytest.raises(ValueError):
            parse_combo("ctrl+alt+f1")


class TestLoadHotkeys:
    def test_defaults_without_config(self, tmp_path):
        cfg = load_hotkeys(tmp_path / "missing.toml")
        assert cfg.capture == DEFAULT_CAPTURE_HOTKEY == "alt+w"
        assert cfg.quick_ocr == DEFAULT_QUICK_OCR_HOTKEY == "alt+x"

    def test_override_from_file(self, tmp_path):
        p = tmp_path / "config.toml"
        p.write_text('[hotkey]\ncapture = "ctrl+alt+s"\nquick_ocr = "ctrl+alt+d"\n',
                     encoding="utf-8")
        cfg = load_hotkeys(p)
        assert cfg.capture == "ctrl+alt+s"
        assert cfg.quick_ocr == "ctrl+alt+d"

    def test_invalid_combo_falls_back(self, tmp_path):
        p = tmp_path / "config.toml"
        p.write_text('[hotkey]\ncapture = "f13"\n', encoding="utf-8")
        cfg = load_hotkeys(p)
        assert cfg.capture == DEFAULT_CAPTURE_HOTKEY

    def test_malformed_toml_falls_back(self, tmp_path):
        p = tmp_path / "config.toml"
        p.write_text("not [valid toml", encoding="utf-8")
        cfg = load_hotkeys(p)
        assert cfg.capture == DEFAULT_CAPTURE_HOTKEY
