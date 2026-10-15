"""v0.4 动作：公式 → LaTeX、表格 → Markdown / CSV / JSON。

设计约束（对齐产品定义与 v0.4 roadmap）：
- 两个动作都只在本地做「规则重建」，不联网、不引入依赖。
- OCR 只给出字符与行，不给结构 —— 所以这里是**尽力而为**的结构推断：
  - 公式：把 Unicode 数学符号 / 上下标 / 希腊字母映射成 LaTeX 命令，
    并对 LaTeX 特殊字符做转义。它不做真正的数学排版理解（那需要公式
    OCR 模型），因此结果以「可编辑的 LaTeX 文本」为目标，而非完美还原。
  - 表格：从 OCR 行里按 `|` / 制表符 / 连续空白推断列，重建为 Markdown / CSV / JSON。
- 结果同时给出多种格式：``data["formats"] = {名称: 文本}``，UI 与 CLI 据此切换视图。
"""

from __future__ import annotations

import csv
import io
import json
import re

from ..logutil import get_logger
from ..ocr.base import OCRProvider, WordBox
from .base import Action, ActionContext, ActionResult
from .builtin import OCRAction

log = get_logger()


# ================================================================= formula

# 上下标：Unicode 上下标字符 → 普通字符（随后包成 ^{...} / _{...}）
_SUPERSCRIPTS = {
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
    "⁺": "+", "⁻": "-", "⁼": "=", "⁽": "(", "⁾": ")",
    "ⁿ": "n", "ⁱ": "i",
}
_SUBSCRIPTS = {
    "₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
    "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
    "₊": "+", "₋": "-", "₌": "=", "₍": "(", "₎": ")",
    "ₐ": "a", "ₑ": "e", "ₒ": "o", "ₓ": "x", "ₙ": "n",
}

# 常见数学运算符 / 关系符 / 集合符
_MATH_SYMBOLS = {
    "×": r"\times", "÷": r"\div", "·": r"\cdot", "⋅": r"\cdot",
    "±": r"\pm", "∓": r"\mp", "∗": r"\ast", "∘": r"\circ",
    "≤": r"\le", "≦": r"\le", "≥": r"\ge", "≧": r"\ge",
    "≠": r"\ne", "≈": r"\approx", "≃": r"\simeq", "≡": r"\equiv",
    "∝": r"\propto", "∼": r"\sim", "∞": r"\infty",
    "∑": r"\sum", "∏": r"\prod", "∫": r"\int", "∮": r"\oint",
    "∂": r"\partial", "∇": r"\nabla",
    "∈": r"\in", "∉": r"\notin", "∋": r"\ni",
    "⊂": r"\subset", "⊆": r"\subseteq", "⊃": r"\supset", "⊇": r"\supseteq",
    "∪": r"\cup", "∩": r"\cap", "∧": r"\wedge", "∨": r"\vee",
    "∀": r"\forall", "∃": r"\exists", "∄": r"\nexists",
    "→": r"\to", "←": r"\leftarrow", "↔": r"\leftrightarrow",
    "⇒": r"\Rightarrow", "⇐": r"\Leftarrow", "⇔": r"\Leftrightarrow",
    "…": r"\ldots", "⋯": r"\cdots", "′": "'", "″": "''", "°": r"^\circ",
}

# 希腊字母
_GREEK = {
    "α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta",
    "ε": r"\epsilon", "ζ": r"\zeta", "η": r"\eta", "θ": r"\theta",
    "ι": r"\iota", "κ": r"\kappa", "λ": r"\lambda", "μ": r"\mu",
    "ν": r"\nu", "ξ": r"\xi", "π": r"\pi", "ρ": r"\rho",
    "σ": r"\sigma", "ς": r"\varsigma", "τ": r"\tau", "υ": r"\upsilon",
    "φ": r"\phi", "χ": r"\chi", "ψ": r"\psi", "ω": r"\omega",
    "Γ": r"\Gamma", "Δ": r"\Delta", "Θ": r"\Theta", "Λ": r"\Lambda",
    "Ξ": r"\Xi", "Π": r"\Pi", "Σ": r"\Sigma", "Φ": r"\Phi",
    "Ψ": r"\Psi", "Ω": r"\Omega",
}

_MATH_CHARS = set(_MATH_SYMBOLS) | set(_GREEK) | set(_SUPERSCRIPTS) | set(_SUBSCRIPTS)

_LATEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "{": r"\{", "}": r"\}",
    "~": r"\textasciitilde{}",
}

_SQRT = re.compile(r"√\s*(\([^)]*\)|[A-Za-z0-9]+)")


def _to_halfwidth(text: str) -> str:
    """全角 ASCII、全角空格 → 半角（只做码位平移，不碰其它字符）。"""
    out = []
    for ch in text:
        o = ord(ch)
        if 0xFF01 <= o <= 0xFF5E:
            out.append(chr(o - 0xFEE0))
        elif o == 0x3000:
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


def _escape_latex(text: str) -> str:
    return "".join(_LATEX_ESCAPES.get(ch, ch) for ch in text)


def _apply_scripts(text: str, table: dict[str, str], mark: str) -> str:
    """把连续的 Unicode 上/下标字符包成 ^{...} / _{...}。"""
    pattern = "[" + re.escape("".join(table)) + "]+"

    def repl(m: re.Match[str]) -> str:
        body = "".join(table[ch] for ch in m.group())
        return f"{mark}{{{body}}}"

    return re.sub(pattern, repl, text)


def to_latex(text: str) -> str:
    """把 OCR 出的（含 Unicode 数学符号的）文本尽力转成 LaTeX。纯函数，便于测试。"""
    s = _to_halfwidth(text.strip())
    # 先转义 LaTeX 特殊字符（此时 ^ _ 还是普通字符），再插入真正的命令与上下标
    s = _escape_latex(s)
    s = _apply_scripts(s, _SUPERSCRIPTS, "^")
    s = _apply_scripts(s, _SUBSCRIPTS, "_")
    s = _SQRT.sub(lambda m: r"\sqrt{" + m.group(1).strip("()") + "}", s)
    for src, dst in {**_MATH_SYMBOLS, **_GREEK}.items():
        s = s.replace(src, dst)
    return s


class FormulaToLatexAction(Action):
    """OCR → LaTeX：Unicode 数学符号 / 上下标 / 希腊字母映射 + 特殊字符转义。

    说明：这是离线规则转换，输出用于「复制到论文/笔记再微调」，不是公式排版引擎。
    """

    id = "formula"
    name = "公式转 LaTeX"
    hint = "数学符号 → LaTeX"
    shortcut = "8"

    def __init__(self, ocr_provider: OCRProvider) -> None:
        self.ocr_provider = ocr_provider

    def execute(self, ctx: ActionContext) -> ActionResult:
        ocr = OCRAction(self.ocr_provider).execute(ctx)
        if not ocr.ok:
            return ocr
        raw = ocr.text
        latex = to_latex(raw)
        display = f"$$\n{latex}\n$$"
        has_math = any(ch in _MATH_CHARS for ch in raw) or bool(
            re.search(r"[=+\-*/^]", raw)
        )
        note = "" if has_math else (
            "\n\n> 未检测到明显的数学符号：结果按原文做了 LaTeX 安全转义，可直接编辑。"
        )
        return ActionResult(
            self.id,
            ok=True,
            text=latex,
            markdown=display + note,
            data={
                **ocr.data,
                "latex": latex,
                "has_math": has_math,
                "formats": {"LaTeX": latex, "LaTeX（显示式）": display},
            },
            elapsed_ms=ocr.elapsed_ms,
        )


# =================================================================== table

_CELL_SPLIT = re.compile(r"\s{2,}")
_MD_SEPARATOR = re.compile(r"^[\s:\-|+]+$")


def _split_row(line: str) -> list[str] | None:
    """把一行切成单元格：优先 `|`，其次制表符，最后连续空白。切不出多列返回 None。"""
    stripped = line.strip()
    if stripped.count("|") >= 2:
        inner = stripped.strip("|")
        return [c.strip() for c in inner.split("|")]
    if "\t" in stripped:
        return [c.strip() for c in stripped.split("\t")]
    if _CELL_SPLIT.search(stripped):
        return [c.strip() for c in _CELL_SPLIT.split(stripped)]
    return None


def _unique_headers(header: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for i, h in enumerate(header):
        name = h or f"col{i + 1}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        out.append(name)
    return out


def _to_markdown(header: list[str], rows: list[list[str]]) -> str:
    def esc(cell: str) -> str:
        return cell.replace("|", r"\|")

    lines = [
        "| " + " | ".join(esc(c) for c in header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(esc(c) for c in row) + " |")
    return "\n".join(lines)


def _to_csv(header: list[str], rows: list[list[str]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue().rstrip("\n")


def _to_json(header: list[str], rows: list[list[str]]) -> str:
    records = [dict(zip(header, row)) for row in rows]
    return json.dumps(records, ensure_ascii=False, indent=2)


def parse_table(lines: list[str]) -> tuple[list[str], list[list[str]]] | None:
    """从 OCR 行重建表格：返回 (header, rows)；不像表格时返回 None。"""
    structured: list[list[str]] = []
    for line in lines:
        if not line.strip():
            continue
        # 跳过 markdown 分隔行 / 纯分隔线（----+----）
        if _MD_SEPARATOR.match(line) and not re.search(r"\w", line):
            continue
        cells = _split_row(line)
        if cells is not None and len(cells) >= 2:
            structured.append(cells)
    if len(structured) < 2:  # 至少表头 + 一行数据
        return None
    ncols = max(len(r) for r in structured)
    padded = [r + [""] * (ncols - len(r)) for r in structured]
    header = _unique_headers(padded[0])
    rows = padded[1:]
    return header, rows


NO_TABLE = (
    "未识别到表格结构 —— 选区里可能没有表格，或列之间缺少清晰分隔"
    "（需要明显的空白、制表符或 `|`）。可尝试框选更完整的表格区域后重试。"
)


# ---- 基于词包围盒的列重建（对「Windows OCR 折叠空白」是关键）----------

def _median_char_width(word_boxes: list[list[WordBox]]) -> float:
    widths = [
        (w.x1 - w.x0) / len(w.text)
        for row in word_boxes for w in row
        if w.text and w.x1 > w.x0
    ]
    widths.sort()
    return widths[len(widths) // 2] if widths else 0.0


def _row_cells(words: list[WordBox], thr: float) -> list[list[WordBox]]:
    """把一行内相邻词按水平间距归组为单元格（词间距 > thr 视为换列）。"""
    words = sorted(words, key=lambda w: w.x0)
    cells = [[words[0]]]
    for prev, w in zip(words, words[1:]):
        if w.x0 - prev.x1 > thr:
            cells.append([w])
        else:
            cells[-1].append(w)
    return cells


def _group_rows(words: list[WordBox], y_thr: float) -> list[list[WordBox]]:
    """按 y 方向把词聚成行。

    Windows OCR 的 ``lines`` 不保证是视觉行（实测在列间距大的图上会按词拆分），
    所以这里忽略 OCR 的行分组，直接用词的纵坐标重新聚类，行内再按 x 排序。
    """
    rows: list[list[WordBox]] = []
    for w in sorted(words, key=lambda w: (w.y0, w.x0)):
        center = (w.y0 + w.y1) / 2
        for row in rows:
            ref = row[0]
            if abs(center - (ref.y0 + ref.y1) / 2) <= y_thr:
                row.append(w)
                break
        else:
            rows.append([w])
    for row in rows:
        row.sort(key=lambda w: w.x0)
    return rows


def parse_table_boxes(word_boxes: list[list[WordBox]]) -> tuple[list[str], list[list[str]]] | None:
    """用词包围盒重建表格：按 y 聚行、按 x 大间距切单元格，再按左边缘聚类成列。

    这是「截图表格」的正解——Windows OCR 会把列间空白折叠、甚至按词拆行，
    但每个词的包围盒保留了几何位置，据此可自行恢复行与列。
    """
    words = [w for row in word_boxes for w in row]
    if len(words) < 4:
        return None
    char_w = _median_char_width(word_boxes)
    if char_w <= 0:
        return None
    heights = sorted(w.y1 - w.y0 for w in words if w.y1 > w.y0)
    med_h = heights[len(heights) // 2] if heights else 0.0
    y_thr = max(med_h * 0.6, 1.0)
    x_thr = max(2.0 * char_w, 6.0)

    rows = _group_rows(words, y_thr)
    if len(rows) < 2:
        return None

    cell_rows: list[list[tuple[float, str]]] = []
    for row in rows:
        cells = _row_cells(row, x_thr)
        cell_rows.append([(c[0].x0, " ".join(w.text for w in c)) for c in cells])

    lefts = sorted(left for row in cell_rows for left, _ in row)
    clusters: list[list[float]] = []
    for x in lefts:
        if clusters and x - clusters[-1][-1] <= x_thr:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    col_left = [sum(c) / len(c) for c in clusters]
    ncols = len(col_left)
    if ncols < 2:
        return None

    grid: list[list[str]] = []
    for row in cell_rows:
        cells = [""] * ncols
        for left, text in row:
            idx = min(range(ncols), key=lambda i: abs(col_left[i] - left))
            cells[idx] = f"{cells[idx]} {text}".strip()
        grid.append(cells)
    if len(grid) < 2:
        return None
    return _unique_headers(grid[0]), grid[1:]


class TableToMarkdownAction(Action):
    """OCR → 表格（Markdown / CSV / JSON）。

    优先用词的包围盒重建行列（抗 Windows OCR 折叠空白 / 按词拆行）；
    没有坐标信息时，退化为按 OCR 行内的 `|`、制表符或连续空白切列。
    重建是尽力而为，结果同时提供三种格式供复制。
    """

    id = "table"
    name = "表格转 Markdown"
    hint = "Markdown / CSV / JSON"
    shortcut = "9"

    def __init__(self, ocr_provider: OCRProvider) -> None:
        self.ocr_provider = ocr_provider

    def execute(self, ctx: ActionContext) -> ActionResult:
        ocr = OCRAction(self.ocr_provider).execute(ctx)
        if not ocr.ok:
            return ocr
        lines = ocr.data.get("lines") or ocr.text.splitlines()
        parsed = None
        boxes = ocr.data.get("word_boxes")
        if boxes:
            parsed = parse_table_boxes(boxes)
        if parsed is None:
            parsed = parse_table(lines)
        if parsed is None:
            return ActionResult(self.id, ok=False, error=NO_TABLE, data=ocr.data,
                                elapsed_ms=ocr.elapsed_ms)
        header, rows = parsed
        md = _to_markdown(header, rows)
        csv_text = _to_csv(header, rows)
        json_text = _to_json(header, rows)
        return ActionResult(
            self.id,
            ok=True,
            text=md,
            markdown=md,
            data={
                **ocr.data,
                "header": header,
                "rows": rows,
                "row_count": len(rows),
                "col_count": len(header),
                "formats": {"Markdown": md, "CSV": csv_text, "JSON": json_text},
            },
            elapsed_ms=ocr.elapsed_ms,
        )
