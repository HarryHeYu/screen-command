"""v0.4 动作测试：公式 → LaTeX（符号/上下标/转义）与表格 → Markdown/CSV/JSON。"""

from __future__ import annotations

import csv
import io
import json

import pytest

from screen_command.actions import (
    ActionContext,
    FormulaToLatexAction,
    TableToMarkdownAction,
    build_default_actions,
    clear_actions,
)
from screen_command.actions.v04 import (
    NO_TABLE,
    parse_table,
    parse_table_boxes,
    to_latex,
)
from screen_command.ocr import MockOcrProvider
from screen_command.ocr.base import OcrResult, WordBox


def _ocr_lines(*lines: str) -> OcrResult:
    return OcrResult(text="\n".join(lines), lines=list(lines), provider="mock")


@pytest.fixture
def provider():
    return MockOcrProvider("placeholder")


class TestToLatex:
    def test_superscript_and_subscript(self):
        assert to_latex("a² + b² = c²") == "a^{2} + b^{2} = c^{2}"
        assert to_latex("x₁ ≤ y") == "x_{1} \\le y"

    def test_greek_and_operators(self):
        assert to_latex("α × β") == "\\alpha \\times \\beta"

    def test_sqrt_wraps_following_token(self):
        assert to_latex("√2") == "\\sqrt{2}"
        assert to_latex("√(a+b)") == "\\sqrt{a+b}"

    def test_latex_specials_escaped(self):
        assert to_latex("50% off") == "50\\% off"
        # 下划线 / 插入符是上下标的自然写法，保留为数学标记，不转义
        assert to_latex("x_1 + y^2") == "x_1 + y^2"
        assert to_latex("a&b") == "a\\&b"

    def test_fullwidth_normalized(self):
        assert to_latex("ａ ≤ ｂ") == "a \\le b"


class TestFormulaToLatexAction:
    def test_math_output_and_formats(self, provider, monkeypatch):
        monkeypatch.setattr(
            MockOcrProvider, "recognize",
            lambda self, png, language=None: _ocr_lines("E = mc²", "α + β = γ"),
        )
        r = FormulaToLatexAction(MockOcrProvider()).execute(ActionContext(image_png=b"i"))
        assert r.ok
        assert r.data["latex"].startswith("E = mc^{2}")
        assert "\\alpha" in r.text
        assert r.markdown.startswith("$$")
        assert set(r.data["formats"]) == {"LaTeX", "LaTeX（显示式）"}
        assert r.data["has_math"] is True

    def test_plain_text_still_ok_with_note(self, provider, monkeypatch):
        monkeypatch.setattr(
            MockOcrProvider, "recognize",
            lambda self, png, language=None: _ocr_lines("plain words here"),
        )
        r = FormulaToLatexAction(MockOcrProvider()).execute(ActionContext(image_png=b"i"))
        assert r.ok
        assert r.data["has_math"] is False
        assert "未检测到" in r.markdown

    def test_ocr_failure_propagates(self):
        class Failing:
            name = "f"

            def is_available(self):
                return True

            def recognize(self, png, language=None):
                raise RuntimeError("ocr down")

        r = FormulaToLatexAction(Failing()).execute(ActionContext(image_png=b"x"))  # type: ignore[arg-type]
        assert not r.ok
        assert "ocr down" in r.error


class TestParseTable:
    def test_pipe_rows(self):
        parsed = parse_table([
            "| Name | Qty | Price |",
            "|---|---|---|",
            "| Apple | 3 | 1.20 |",
            "| Banana | 12 | 0.50 |",
        ])
        assert parsed == (
            ["Name", "Qty", "Price"],
            [["Apple", "3", "1.20"], ["Banana", "12", "0.50"]],
        )

    def test_whitespace_columns(self):
        parsed = parse_table(["Name    Qty", "Apple   3", "Banana  12"])
        assert parsed == (["Name", "Qty"], [["Apple", "3"], ["Banana", "12"]])

    def test_tab_columns(self):
        parsed = parse_table(["A\tB\tC", "1\t2\t3"])
        assert parsed == (["A", "B", "C"], [["1", "2", "3"]])

    def test_ragged_rows_padded(self):
        parsed = parse_table(["A  B  C", "1  2"])
        assert parsed == (["A", "B", "C"], [["1", "2", ""]])

    def test_not_a_table(self):
        assert parse_table(["just a sentence", "another line"]) is None

    def test_duplicate_headers_uniquified(self):
        header, _ = parse_table(["x  x", "1  2"])  # type: ignore[misc]
        assert header == ["x", "x_1"]


class TestParseTableBoxes:
    @staticmethod
    def _wb(text, x0, x1, y=0):
        return WordBox(text=text, x0=x0, y0=y, x1=x1, y1=y + 20)

    def test_columns_recovered_from_geometry(self):
        boxes = [
            [self._wb("Name", 0, 40, 0), self._wb("Qty", 200, 230, 0), self._wb("Price", 300, 350, 0)],
            [self._wb("Apple", 0, 50, 30), self._wb("3", 200, 210, 30), self._wb("1.20", 300, 340, 30)],
            [self._wb("Banana", 0, 60, 60), self._wb("12", 200, 225, 60), self._wb("0.50", 300, 340, 60)],
        ]
        assert parse_table_boxes(boxes) == (
            ["Name", "Qty", "Price"],
            [["Apple", "3", "1.20"], ["Banana", "12", "0.50"]],
        )

    def test_multiword_cell_kept_together(self):
        boxes = [
            [self._wb("New", 0, 30, 0), self._wb("York", 35, 70, 0), self._wb("100", 200, 230, 0)],
            [self._wb("San", 0, 25, 30), self._wb("Francisco", 30, 110, 30), self._wb("200", 200, 230, 30)],
        ]
        header, rows = parse_table_boxes(boxes)  # type: ignore[misc]
        assert header == ["New York", "100"]
        assert rows == [["San Francisco", "200"]]

    def test_regroups_rows_by_y_not_ocr_line(self):
        """OCR 可能把每个词单独成行（实测），按 y 重新聚行后仍应还原表格。"""
        boxes = [
            [self._wb("Name", 0, 40, 0)],
            [self._wb("Qty", 200, 230, 0)],
            [self._wb("Apple", 0, 50, 30)],
            [self._wb("3", 200, 210, 30)],
        ]
        assert parse_table_boxes(boxes) == (
            ["Name", "Qty"], [["Apple", "3"]]
        )

    def test_single_column_is_not_a_table(self):
        boxes = [[self._wb("hello", 0, 40, 0)], [self._wb("world", 0, 40, 30)]]
        assert parse_table_boxes(boxes) is None


class TestTableToMarkdownAction:
    def _run(self, monkeypatch, *lines: str):
        monkeypatch.setattr(
            MockOcrProvider, "recognize",
            lambda self, png, language=None: _ocr_lines(*lines),
        )
        return TableToMarkdownAction(MockOcrProvider()).execute(ActionContext(image_png=b"i"))

    def test_uses_word_boxes_when_text_lost_columns(self, monkeypatch):
        """模拟 Windows OCR：text 把列折叠成单空格，但包围盒仍能还原列。"""
        boxes = [
            [WordBox("Name", 0, 0, 40, 20), WordBox("Qty", 200, 0, 230, 20)],
            [WordBox("Apple", 0, 30, 50, 50), WordBox("3", 200, 30, 210, 50)],
            [WordBox("Banana", 0, 60, 60, 80), WordBox("12", 200, 60, 225, 80)],
        ]
        monkeypatch.setattr(
            MockOcrProvider, "recognize",
            lambda self, png, language=None: OcrResult(
                text="Name Qty\nApple 3\nBanana 12",
                lines=["Name Qty", "Apple 3", "Banana 12"],
                provider="mock",
                word_boxes=boxes,
            ),
        )
        r = TableToMarkdownAction(MockOcrProvider()).execute(ActionContext(image_png=b"i"))
        assert r.ok
        assert "| Name | Qty |" in r.text
        assert "| Apple | 3 |" in r.text

    def test_formats_all_present(self, monkeypatch):
        r = self._run(monkeypatch, "Name  Qty  Price", "Apple  3  1.20", "Banana  12  0.50")
        assert r.ok
        formats = r.data["formats"]
        assert set(formats) == {"Markdown", "CSV", "JSON"}
        assert formats["Markdown"] == r.text
        assert "| Name | Qty | Price |" in r.text
        assert "| --- | --- | --- |" in r.text
        # CSV 可被标准库解析回原表格
        rows = list(csv.reader(io.StringIO(formats["CSV"])))
        assert rows[0] == ["Name", "Qty", "Price"]
        assert rows[1] == ["Apple", "3", "1.20"]
        # JSON 是「表头 → 值」的字典列表
        records = json.loads(formats["JSON"])
        assert records[0] == {"Name": "Apple", "Qty": "3", "Price": "1.20"}
        assert len(records) == 2

    def test_not_a_table_degrades(self, monkeypatch):
        r = self._run(monkeypatch, "hello world", "no columns here")
        assert not r.ok
        assert r.error == NO_TABLE

    def test_pipe_in_cell_escaped_in_markdown(self, monkeypatch):
        r = self._run(monkeypatch, "A  B", "x|y  1")  # 空白分隔，单元格内含 |
        assert r.ok
        # 该行含 2 个分隔符？只 1 个 → 走空白分隔，单元格 "x|y" 需转义
        assert r"x\|y" in r.data["formats"]["Markdown"]


class TestV04Registry:
    def test_default_actions_include_v04_with_shortcuts(self, provider):
        clear_actions()
        actions = build_default_actions(provider)
        ids = [a.id for a in actions]
        assert ids == ["ocr", "copy_text", "translate", "code", "markdown",
                       "explain", "save_image", "formula", "table"]
        by_id = {a.id: a for a in actions}
        assert by_id["formula"].shortcut == "8"
        assert by_id["table"].shortcut == "9"
