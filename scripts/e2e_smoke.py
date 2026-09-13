"""E2E 冒烟测试：整条链路在真实屏幕上自动化验证。

    .venv/Scripts/python scripts/e2e_smoke.py

流程：
1. 在屏幕上显示一个已知文字的目标窗口（英文 + 中文）
2. 触发 start_capture（真实全屏快照 + overlay）
3. QTest 在目标文字区域模拟按下/拖动/松开（真实框选交互）
4. 直接触发 OCRAction（等价于在 Action Menu 里按 "1"）
5. 等待后台 OCR 完成，断言 Result Window 内容包含关键词
6. 附加验证：Esc 取消路径、热键注册状态

退出码 0 = PASS。全程无持久系统修改。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtCore import QPoint, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget  # noqa: E402

from screen_command.actions.base import ActionContext  # noqa: E402
from screen_command.app import AppController, IDLE  # noqa: E402

EN_SENTINEL = "User location is not supported"
ZH_SENTINEL = "机器学习是人工智能"


class TargetWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("E2E Target")
        # 置顶显示，保证快照时目标文字在最上层（真实桌面可能有其他窗口）
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Window
        )
        layout = QVBoxLayout(self)
        f_en = QFont("Arial")
        f_en.setPointSize(16)
        f_zh = QFont("Microsoft YaHei")
        f_zh.setPointSize(14)
        l1 = QLabel("User location is not supported for the API use.")
        l1.setFont(f_en)
        l2 = QLabel(ZH_SENTINEL + "，用于端到端测试。")
        l2.setFont(f_zh)
        for l in (l1, l2):
            l.setStyleSheet("background: white; color: black; padding: 8px;")
            layout.addWidget(l)


def main() -> int:
    app = QApplication(sys.argv)
    controller = AppController()

    # 1. 目标窗口：放在主屏固定位置并等它真正渲染到屏幕上
    target = TargetWindow()
    target.move(120, 120)
    target.resize(520, 140)
    target.show()
    target.raise_()
    target.activateWindow()
    for _ in range(60):
        app.processEvents()
        time.sleep(0.05)
    geo = target.geometry()
    print(f"[1] target window at {geo.x()},{geo.y()} {geo.width()}x{geo.height()}")

    hotkey_ok = None
    controller.run()
    for _ in range(30):
        app.processEvents()
        if controller._hotkey and "ctrl+shift+a" in controller._hotkey.registered_combos:
            hotkey_ok = True
            break
        if controller._hotkey and not controller._hotkey.is_alive():
            hotkey_ok = False
            break
        time.sleep(0.1)
    print(f"[2] global hotkey registered: {hotkey_ok} ({controller._hotkey.registered_combos})")

    # 3. 触发 capture，真实快照 + overlay
    controller.start_capture()
    for _ in range(30):
        app.processEvents()
        time.sleep(0.05)
    assert controller.state == "capturing", f"state={controller.state}"
    print(f"[3] capturing, {len(controller._overlays)} overlay(s) shown")

    # 4. 在目标文字区域模拟拖拽（局部坐标换算）
    overlay = next(
        (ov for ov in controller._overlays if ov.geometry().intersects(geo)), None
    )
    assert overlay is not None, "no overlay over target screen"
    tl = geo.topLeft() - overlay.geometry().topLeft()
    br = geo.bottomRight() - overlay.geometry().topLeft() - QPoint(6, 6)
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, tl + QPoint(4, 4))
    for i in range(1, 8):
        step = tl + (br - tl) * i / 7 + QPoint(4, 4)
        QTest.mouseMove(overlay, step)
        app.processEvents()
        time.sleep(0.03)
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, br)
    for _ in range(20):
        app.processEvents()
        time.sleep(0.05)
    assert controller.state == "choosing-action", f"state={controller.state}"
    assert controller._region is not None
    print(f"[4] selected {controller._region.width()}x{controller._region.height()} px, menu shown")

    # 5. 真实点击菜单里的第一个动作按钮（OCR），等待后台完成
    #    注意：不能直接 close() 菜单 —— hideEvent 会补发 cancelled（P1 修复行为），
    #    状态会回到 Idle。通过真实按钮点击走 _pick 路径，顺带验证菜单接线。
    from PySide6.QtWidgets import QPushButton

    assert controller._menu is not None, "menu not shown"
    menu_buttons = controller._menu.findChildren(QPushButton)
    assert menu_buttons, "menu has no buttons"
    QTest.mouseClick(menu_buttons[0], Qt.MouseButton.LeftButton)
    deadline = time.time() + 30
    while time.time() < deadline:
        app.processEvents()
        if controller._result_win is not None and controller.state == "showing-result":
            # 等文本填充
            text = controller._result_win._text.toPlainText()
            if text.strip():
                break
        time.sleep(0.05)
    else:
        print("FAIL: OCR did not finish in 30s")
        return 1
    text = controller._result_win._text.toPlainText()
    print(f"[5] OCR result ({len(text)} chars): {text[:100]!r}")
    ok_en = EN_SENTINEL.lower() in text.lower()
    ok_zh = ZH_SENTINEL in text.replace(" ", "")
    print(f"    english sentinel: {ok_en}, chinese sentinel: {ok_zh}")

    # 6. Esc 取消路径
    controller.start_capture()
    for _ in range(20):
        app.processEvents()
        time.sleep(0.05)
    assert controller.state == "capturing"
    QTest.keyClick(controller._overlays[0], Qt.Key.Key_Escape)
    for _ in range(10):
        app.processEvents()
        time.sleep(0.05)
    cancel_ok = controller.state == IDLE
    print(f"[6] Esc cancel returns to idle: {cancel_ok}")

    controller.shutdown()
    for _ in range(10):
        app.processEvents()
        time.sleep(0.05)

    passed = ok_en and ok_zh and cancel_ok
    print(f"\n{'PASS' if passed else 'FAIL'}: e2e smoke")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
