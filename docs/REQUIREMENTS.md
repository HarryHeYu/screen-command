# 系统需求与约束记录

本文档记录两类内容：
1. 运行 Screen Command 开发版的**项目本地依赖**（全部在 `.venv`，未触碰系统）。
2. **未满足的系统性需求** —— 如果未来某功能必须系统级安装，只在这里登记，不擅自执行。

## 项目本地依赖（pip，安装于 .venv，project-local）

| 包 | 用途 |
|---|---|
| PySide6 6.11 | GUI：overlay / menu / result window |
| winrt-runtime + winrt-Windows.* 3.2.1 | 调用 Windows 内置 OCR（Windows.Media.Ocr） |
| Pillow | 测试图片生成 / 图片格式转换 |
| pytest | 测试 |

## 运行环境要求

- Windows 10 1809+（Windows.Media.Ocr 自带，语言包 en-US / zh-Hans-CN 已确认存在）
- Python 3.12（3.11–3.13 均可，winrt 3.2 wheel 覆盖范围）
- 无需管理员权限；无需联网（OCR 本地执行）

## 未满足的系统性需求（登记，不执行）

当前无。潜在候选（均非必需，仅备忘）：

- **Tesseract OCR**：若未来需要 WinRT OCR 覆盖不了的语言/场景，
  可能需要系统安装 Tesseract 及语言包 → 届时优先评估 RapidOCR（pip 即可，project-local）。
- **开机自启 / 全局热键持久化**：产品明确不需要；当前热键为运行期注册，退出即失效。

## 禁止清单（开发期间持续有效）

系统级 installer / 全局安装 / 修改 PATH / 注册表 / Windows Service /
开机启动 / Program Files / Explorer shell extension / 系统安全策略 /
默认应用 / 持久系统快捷键 —— 一律不做。
