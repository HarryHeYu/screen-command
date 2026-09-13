# Screen Command

[English](README.md) | [简体中文](README.zh-CN.md)

框选屏幕上的任意区域，立即对内容执行 OCR、翻译、代码提取、解释报错等动作，结果直接可用。

它把「截图 → 保存 → 打开工具 → 上传 → 粘贴 → 输入指令」压缩成一次交互：看到什么，框什么，直接处理。

## 功能

- **框选截图**：全屏暗色遮罩上拖拽选区，实时显示选区尺寸，Esc 取消；支持多显示器与 DPI 缩放。
- **本地 OCR**：使用 Windows 内置 OCR 引擎（Windows.Media.Ocr），支持中英文，完全本地运行，无需联网。
- **动作系统**：识别文字（OCR）、复制文字、翻译、提取代码、转 Markdown、解释错误、保存截图，通过框选后的浮动菜单选择，数字键直选。
- **解释错误**：对报错输出做离线规则分析（Python traceback、CUDA OOM、git、Node.js、MSVC/MinGW、shell 错误），可选接入 LLM 增强。
- **Quick Action**：`Ctrl+Shift+1` 框选后直接 OCR 并复制到剪贴板，不弹菜单。
- **测试 harness**：CLI 可对图片文件直接执行任意动作，自动化测试无需真实屏幕。

## 运行

依赖 Python 3.11–3.13（Windows 10 1809+）。所有依赖安装在项目内虚拟环境，不写入系统。

```bash
cd screen-command
python -m venv .venv
.venv\Scripts\python -m pip install -e .

# 启动
.venv\Scripts\python -m screen_command run
```

启动后按 `Ctrl+Shift+A` 框选，或点击状态窗口的 Capture 按钮。快捷键为运行期注册，程序退出即释放，不修改任何系统设置。如果快捷键被其他软件占用，注册会失败并提示，Capture 按钮始终可用。

## CLI

```bash
screen_command run            # 启动 GUI
screen_command providers      # 查看可用 OCR provider 与语言包
screen_command process <img> --action ocr|copy_text|translate|code|markdown|explain|save_image
    [--provider auto|windows|mock] [--language zh-Hans-CN]
    [--output result.txt] [--md] [--opt KEY VALUE ...]
```

## 快捷键

| 快捷键 | 行为 |
|---|---|
| `Ctrl+Shift+A` | 框选屏幕区域，弹出动作菜单 |
| `Ctrl+Shift+1` | 框选 → OCR → 复制到剪贴板 |

## 测试

```bash
.venv\Scripts\python -m pytest tests -v       # 单元与集成测试
.venv\Scripts\python scripts/e2e_smoke.py     # 真实屏幕全链路冒烟
```

测试图片由 `tests/make_fixtures.py` 生成（英文 / 中文 / 混合 / 终端报错 / 代码 / 小字号）。

## 质量预期

翻译、提取代码、转 Markdown、解释错误均以 OCR 原始识别质量为上限，规则后处理（缩进重建、全角归一、行号剥离）不做字符纠错。深色终端小号等宽字体存在典型混淆（`l↔1`、`O↔0`），识别要求高的场景建议框选更大区域、避开小字号和低对比度内容。选区跨多块屏幕时，按选区中心所在屏幕裁剪。

## 隐私

默认 local-first：截图与 OCR 全部在本机完成，程序没有任何网络代码，不联网、不上传。翻译/LLM 动作基于 provider 抽象，项目未捆绑任何实现；未配置时相关动作显示明确的 unavailable 提示，其余功能不受影响。

## 项目结构

```
src/screen_command/
  capture.py        屏幕快照与区域裁剪（内存操作，不落盘）
  overlay.py        框选遮罩层
  hotkey.py         全局快捷键（进程生命周期内有效）
  app.py            状态机与流程编排
  providers.py      Translation / LLM provider 抽象
  ocr/              OCRProvider 抽象 + Windows OCR + Mock
  actions/          Action 抽象、注册表与各动作实现
  ui/               动作菜单 / 结果窗口 / 状态窗口
tests/              pytest 测试与测试图片生成
scripts/            e2e 冒烟脚本
docs/               ROADMAP / ARCHITECTURE / DECISIONS / REQUIREMENTS
```

设计细节见 [ARCHITECTURE.md](docs/ARCHITECTURE.md) 与 [DECISIONS.md](docs/DECISIONS.md)。
