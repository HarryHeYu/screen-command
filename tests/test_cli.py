"""CLI harness 测试：process 子命令端到端（mock provider，无需屏幕）。"""

from __future__ import annotations

import pytest

from screen_command import __version__
from screen_command.__main__ import main


def test_process_ocr_mock(capsys, fixtures):
    rc = main(["process", str(fixtures["en_paragraph.png"]),
               "--action", "ocr", "--provider", "mock"])
    out = capsys.readouterr()
    assert rc == 0
    assert "mock recognized text" in out.out


def test_process_output_file(capsys, fixtures, tmp_path):
    out_file = tmp_path / "result.txt"
    rc = main(["process", str(fixtures["zh_paragraph.png"]),
               "--action", "ocr", "--provider", "mock",
               "--output", str(out_file)])
    capsys.readouterr()
    assert rc == 0
    assert "第二行中文内容" in out_file.read_text(encoding="utf-8")


def test_process_bad_image(capsys):
    rc = main(["process", "no/such/file.png", "--action", "ocr",
               "--provider", "mock"])
    err = capsys.readouterr()
    assert rc == 2
    assert "cannot read" in err.err


def test_process_unknown_action(capsys, fixtures):
    rc = main(["process", str(fixtures["en_paragraph.png"]),
               "--action", "warp", "--provider", "mock"])
    err = capsys.readouterr()
    assert rc == 2
    assert "unknown action" in err.err


def test_process_formula_action(capsys, fixtures):
    rc = main(["process", str(fixtures["en_paragraph.png"]),
               "--action", "formula", "--provider", "mock"])
    out = capsys.readouterr()
    assert rc == 0
    assert out.out.strip()  # mock 文本也能产出 LaTeX 文本


def test_process_table_action_without_table_fails(capsys, fixtures):
    # mock provider 返回普通文本，不含列 → 表格动作应明确失败（rc=1）
    rc = main(["process", str(fixtures["en_paragraph.png"]),
               "--action", "table", "--provider", "mock"])
    err = capsys.readouterr()
    assert rc == 1
    assert "表格" in err.err


def test_process_unknown_format(capsys, fixtures):
    rc = main(["process", str(fixtures["en_paragraph.png"]),
               "--action", "ocr", "--provider", "mock", "--format", "CSV"])
    err = capsys.readouterr()
    assert rc == 2
    assert "unknown format" in err.err


def test_providers_command(capsys):
    rc = main(["providers"])
    out = capsys.readouterr()
    assert rc == 0
    assert "windows" in out.out and "mock" in out.out


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as ei:
        main(["--version"])
    assert ei.value.code == 0
    assert __version__ in capsys.readouterr().out
