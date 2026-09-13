# Screen Command

> **框一下，屏幕上的任何内容变成可操作的数据。**
>
> Select anything on screen → understand it → transform it → use the result.

Screen Command 是一个 Windows 优先的桌面效率工具：按下快捷键框选屏幕区域，
立即对选中内容执行 OCR / 翻译 / 解释等动作，结果显示在可复制的窗口中。
它把「截图 → 保存 → 打开工具 → 上传 → 粘贴 → 输入指令」压缩成一次交互。

## 当前状态（v0.2）

核心链路与 v0.2 动作集已实现并验证：

```
触发 Capture（Ctrl+Shift+A）→ Selection Overlay → 拖拽框选 → 截取区域（内存）
→ Action Menu（数字键直选）→ 执行动作 → Result Window（可选中 / 复制 / 重试 / 关闭）
```

- ✅ 多显示器 + DPI 缩放感知（每块屏幕独立 overlay）
- ✅ OCR：英文 / 中文 / 中英混合（Windows.Media.Ocr，完全本地、无需联网）
- ✅ 动作：OCR / 复制文字 / 翻译 / 提取代码 / 转 Markdown / 解释错误 / 保存截图
- ✅ Explain Error：离线规则分析（Python traceback / CUDA OOM / 常见错误），LLM 仅是可选增强
- ✅ Quick Action：`Ctrl+Shift+1` = 框选 → OCR → 复制（跳过菜单）
- ✅ Provider 抽象（Translation / LLM）：未捆绑实现，未配置时优雅降级、绝不静默联网
- ✅ CLI test harness：`python -m screen_command process <image> --action ocr|code|markdown|explain|...`

## 开发运行（project-local，无系统安装）

```bash
# 1. 依赖全部在项目 .venv 内（从未安装到系统）
.venv/Scripts/python -m pip install -e .

# 2. 运行开发版
cmd //c run_dev.bat    # 或: .venv/Scripts/python -m screen_command run

# 3. 对图片直接执行 action（测试 harness，不碰屏幕）
.venv/Scripts/python -m screen_command process tests/fixtures/en_paragraph.png --action ocr

# 4. 跑测试
.venv/Scripts/python -m pytest tests -v
```

程序启动后：按 `Ctrl+Shift+A` 或点击状态窗口的 Capture 按钮进入框选。
`Esc` 取消框选；拖拽结束后弹出动作菜单（数字键 1-7 直选）；结果显示在结果窗口。

## CLI

```bash
screen_command run            # GUI（= capture，两者是别名）
screen_command providers      # 列出可用 OCR provider 与语言包
screen_command process <img> --action ocr|copy_text|translate|code|markdown|explain|save_image
    [--provider auto|windows|mock] [--language zh-Hans-CN]
    [--output result.txt]     # 结果写入文件
    [--md]                    # 有 markdown 视图时（code/markdown）输出 markdown
    [--opt KEY VALUE ...]     # 如 --opt output_path out.png
```

## 快捷键

| 快捷键 | 行为 |
|---|---|
| `Ctrl+Shift+A` | 框选屏幕区域 → 弹出动作菜单 |
| `Ctrl+Shift+1` | 框选 → OCR → 复制到剪贴板（跳过菜单） |

- 快捷键为**运行期注册**（进程退出即释放），不修改系统设置。
- 目前仅支持上述两个硬编码组合。若组合被其他常驻软件（输入法、音乐播放器、
  游戏工具等）占用，注册会失败并在状态窗口提示——Capture 按钮始终可用。
- 状态机：`Idle → Capturing → ChoosingAction → Processing → ShowingResult`。

## 质量预期（OCR 局限）

翻译 / 提取代码 / 转 Markdown / 解释错误均以 **OCR 原始识别质量为上限**，
规则后处理（缩进重建、全角归一、行号剥离）不做字符纠错。已知典型混淆：
深色终端小号等宽字体的 `l↔1`、`O↔0`（call→ca11），艺术字体断词。
对识别要求高的场景建议框选更大区域、避免小字号/低对比度内容。

## 已知边界

- 选区跨越多块屏幕时，仅按选区中心所在的屏幕裁剪（跨屏拼接为后续计划）。

## 项目结构

```
src/screen_command/
  capture.py        Capture Core：屏幕抓取 / 区域裁剪（内存 buffer）
  overlay.py        Selection Overlay：暗色蒙层 / 拖拽 / 尺寸提示 / Esc
  hotkey.py         全局快捷键（运行期注册，仅进程存活期有效）
  app.py            应用生命周期与状态机 (Idle/Capturing/ChoosingAction/Processing/ShowingResult)
  ocr/              OCRProvider 抽象 + Windows OCR / Mock 实现
  actions/          Action 抽象 + 注册表 + OCRAction 等
  ui/               Action Menu / Result Window / 状态窗口
tests/              pytest + 生成的多语言测试图片
docs/               ROADMAP / ARCHITECTURE / DECISIONS / REQUIREMENTS
```

## 隐私

- 默认 **local-first**：截图与 OCR 全部在本机完成，不联网、不上传。
- 未来接入任何第三方 API 的 action，执行前必须明确提示数据去向。

## 约束

开发期间不做任何系统级安装（详见 `docs/REQUIREMENTS.md`）。
程序关闭后不留任何持久性修改。
