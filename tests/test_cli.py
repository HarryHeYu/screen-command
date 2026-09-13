"""CLI harness 测试：process 子命令端到端（mock provider，无需屏幕）。"""

from __future__ import annotations

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


def test_providers_command(capsys):
    rc = main(["providers"])
    out = capsys.readouterr()
    assert rc == 0
    assert "windows" in out.out and "mock" in out.out
