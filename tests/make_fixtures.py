"""生成确定性 OCR 测试图片（tests/fixtures/*.png）。

用 Pillow 绘制固定文字，覆盖第一阶段的测试矩阵：
英文 / 中文 / 混合 / 终端报错（深底）/ 代码 / 小字。
运行 pytest 时由 conftest 自动确保存在。
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FIXTURES = Path(__file__).resolve().parent / "fixtures"

_FONT_DIR = Path(r"C:\Windows\Fonts")


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(_FONT_DIR / name), size)


def _draw(
    path: Path,
    lines: list[tuple[str, ImageFont.FreeTypeFont, str]],
    bg: str,
    *,
    width: int = 900,
    line_gap: int = 10,
) -> None:
    """按 (text, font, color) 列表绘制左对齐文本块。"""
    ascent_pad = 18
    total_h = sum(f.size + line_gap for _, f, _ in lines) + ascent_pad * 2
    img = Image.new("RGB", (width, total_h), bg)
    d = ImageDraw.Draw(img)
    y = ascent_pad
    for text, font, color in lines:
        d.text((24, y), text, font=font, fill=color)
        y += font.size + line_gap
    img.save(path)


def generate_all(force: bool = False) -> dict[str, Path]:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}

    def dest(name: str) -> Path:
        p = FIXTURES / name
        out[name] = p
        return p

    # 1. 英文段落（浅底深字）
    arial24 = _font("arial.ttf", 24)
    _draw(
        dest("en_paragraph.png"),
        [
            ("The quick brown fox jumps over the lazy dog.", arial24, "#1a1a1a"),
            ("User location is not supported for the API use.", arial24, "#1a1a1a"),
            ("Screen Command turns pixels into usable data.", arial24, "#1a1a1a"),
        ],
        "#ffffff",
    )

    # 2. 中文段落（浅底深字，微软雅黑）
    msyh24 = _font("msyh.ttc", 24)
    _draw(
        dest("zh_paragraph.png"),
        [
            ("机器学习是人工智能的一个分支。", msyh24, "#111111"),
            ("深度学习模型需要大量训练数据。", msyh24, "#111111"),
            ("损失函数衡量预测与真实的差距。", msyh24, "#111111"),
        ],
        "#fdfdfd",
    )

    # 3. 中英混合
    _draw(
        dest("mixed.png"),
        [
            ("使用 Python 实现 neural network 训练", msyh24, "#202020"),
            ("准确率 accuracy 达到 92.5%", msyh24, "#202020"),
            ("参考文档 https://pytorch.org docs", msyh24, "#202020"),
        ],
        "#ffffff",
    )

    # 4. 终端报错（深底浅字，等宽）— 深色背景用例
    consol20 = _font("consola.ttf", 20)
    _draw(
        dest("terminal_error.png"),
        [
            ("Traceback (most recent call last):", consol20, "#cccccc"),
            ('  File "train.py", line 42, in <module>', consol20, "#cccccc"),
            ("    loss = criterion(outputs, labels)", consol20, "#cccccc"),
            ("RuntimeError: CUDA out of memory.", consol20, "#f14c4c"),
        ],
        "#1e1e1e",
    )

    # 5. 代码（浅底，等宽，带缩进）
    _draw(
        dest("code.png"),
        [
            ("def train(model, loader):", consol20, "#0b0b0b"),
            ("    model.train()", consol20, "#0b0b0b"),
            ("    for x, y in loader:", consol20, "#0b0b0b"),
            ("        loss = model(x, y)", consol20, "#0b0b0b"),
            ("    return loss", consol20, "#0b0b0b"),
        ],
        "#fafafa",
    )

    # 6. 小字号文本（12px 左右）
    small = _font("arial.ttf", 12)
    _draw(
        dest("small_text.png"),
        [
            ("tiny but readable annotation at 12px", small, "#333333"),
            ("second line of small text 12345", small, "#333333"),
        ],
        "#f5f5f5",
        width=520,
    )

    for p in out.values():
        if force or not p.exists():
            continue
    return out


def ensure_fixtures() -> dict[str, Path]:
    """fixtures 不存在时生成（增量）。"""
    if not all(
        (FIXTURES / n).exists()
        for n in [
            "en_paragraph.png",
            "zh_paragraph.png",
            "mixed.png",
            "terminal_error.png",
            "code.png",
            "small_text.png",
        ]
    ):
        return generate_all(force=True)
    return {p.name: p for p in FIXTURES.glob("*.png") if not p.name.startswith("_")}


if __name__ == "__main__":
    paths = generate_all(force=True)
    for name, path in paths.items():
        print(f"generated {path.name} ({path.stat().st_size // 1024} KB)")
