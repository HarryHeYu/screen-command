# 技术决策记录

记录重要技术选型及原因。后续偏离 roadmap 顺序的调整也记录在此。

## D1. 语言与运行时：Python 3.12（项目内 venv）

**日期**: 2026-09-13

**选择**: Python 3.12 + PySide6，所有依赖装在项目 `.venv`。

**备选与权衡**:
- **Rust**: 二进制小、全局热键成熟，但 OCR（WinRT 绑定）和 GUI 迭代速度明显慢，
  第一阶段「快速、稳定、顺滑」的验证成本太高。
- **C#/.NET**: WinRT OCR 最顺，但本机没有 .NET SDK，且安装 SDK 违反 project-local 约束。
- **Node/Electron**: 二进制巨大，屏幕捕获与 DPI 处理反而绕。
- **Python 3.14**（系统默认）: 部分 native wheel（winrt 系列）尚未跟上 3.14，选 3.12 求稳。

**代价**: 二进制打包后体积偏大（PySide6）。接受；packaging 阶段再优化（可考虑 exclude Qt 模块）。

## D2. GUI / Overlay：PySide6（Qt6）

- Qt6 默认 per-monitor DPI aware，QScreen 抽象天然支持多显示器，每屏一个 overlay 窗口即可。
- 无边框、置顶、半透明 overlay、浮层菜单都是 Qt 成熟能力，不需要 win32 手绘。

## D3. 屏幕捕获：Qt 自身（QScreen.grabWindow），不引入 mss

**关键设计**: 触发框选时**先抓全屏快照、再显示 overlay**，overlay 的背景就是这张
冻结快照（加暗色蒙层）。这样：
- 抓到的图永远不会包含 overlay 自身；
- overlay 显示的是静态图片，拖拽时无闪烁；
- 松开鼠标直接从快照裁剪（QPixmap.copy），全程内存，无临时文件；
- 坐标在同一 Qt 逻辑坐标系内，DPI 换算交给 Qt（crop 时按 devicePixelRatio 转物理像素）。

未选 mss 的原因：mss 需要自己做逻辑坐标→物理像素映射，与 Qt 坐标系割裂，
多屏不同 DPI 时容易错位；Qt 快照与 overlay 坐标天然一致。
Capture Core 的接口设计为「给 region 返回图片 buffer」，底层实现可替换。

## D4. OCR 首个 provider：Windows.Media.Ocr（WinRT），via winrt Python 包

**侦察结果**（2026-09-13，只读探测）: 系统内置 OCR 引擎可用，
已装语言包 `en-US`、`zh-Hans-CN`，最大图像边 10000px —— 恰好覆盖第一阶段的
英文/中文/混合需求，且完全本地、免费、无安装。

- 通过 `winrt-runtime` + `winrt-Windows.*` 包从 Python 调用，全部 pip 装进项目 venv。
- 图片以内存字节 → `InMemoryRandomAccessStream` → `BitmapDecoder` → `SoftwareBitmap`
  传给引擎，无临时文件。
- 语言选择策略：图片内中英混合时 en-US 引擎也能识别中文（Windows OCR 引擎特性），
  provider 暴露 `languages` 并优先用户配置，默认 zh-Hans-CN → en-US 双选。
- **MockOcrProvider** 用于无 GUI/无 WinRT 环境（CI、单元测试）跑通整条 pipeline。
- 未来备选：RapidOCR（onnxruntime，本地、跨平台）作为非 Windows 平台的 provider，
  接口已预留，第一阶段不引入（体积大）。

## D5. 全局快捷键：运行期 RegisterHotKey（ctypes），可接受

产品定义允许：「如果可以通过运行中进程临时注册、不产生持久系统修改，再实现」。
`RegisterHotKey` 是进程生命周期内的注册，程序退出/崩溃后系统自动回收，
**不写注册表、不装服务、不改系统快捷键**，符合全部约束。
实现放在独立线程 + `WM_HOTKEY` 消息循环，触发后 marshal 到 Qt 主线程。
同时保留 GUI 按钮与 CLI 触发路径，热键失败不阻塞核心链路。

## D6. 项目布局：src layout + `python -m screen_command` CLI

- src layout 避免 import 到未安装源码的坑。
- CLI 子命令：`run`（GUI）、`process <img> --action ocr`（测试 harness）、`capture`（= run 的别名，GUI 常驻）、`providers`（列出可用 OCR provider）。
- 测试 harness 使 action 脱离真实屏幕可测，也方便 Agent 自动化验证。

## D7. 状态机

```
Idle → Capturing → ChoosingAction → Processing → ShowingResult → (Idle | Capturing)
        ↑ Esc 取消回到 Idle
```

所有 UI 转移经由 `AppController` 集中管理，避免 overlay / menu / result 各自为政。

## D8. Windows 中文 OCR 输出规整（tidy_cjk_text）

**日期**: 2026-09-13

zh-Hans 引擎输出有两个特性：汉字之间插入空格（"机 器 学 习"）、标点用全角
（"92 ． 5 ％"）。provider 内做无损后处理：
- 折叠「全角标点前后」与「汉字之间」的空格（不碰 CJK 与拉丁词之间的正常空格）；
- 全角 ASCII 变体 → 半角。

保持 OCR 原始行为可通过未来 config 关闭（第一阶段无 config，硬编码开启）。

## D9. 真机验证中的实现细节坑（备忘）

- PySide6 `QPainter.drawPixmap` 不接受 `QRect` 目标 + `QRectF` 源的混用重载，
  两者必须同为 QRectF（overlay 选区亮度还原因此静默失败过一次，E2E 冒烟抓出）。
- `QPixmap.copy(空矩形)` 返回整张图而不是空图 —— crop 需显式判空，
  否则「选区完全在屏幕外」这个边界会静默产出全屏截图。
- WinRT 集合类型（IVectorView）需要单独的 `winrt-Windows.Foundation.Collections` 包。

## D10. v0.2/v0.3 部分 item 的顺序调整与「无 provider 降级」策略

**日期**: 2026-09-13

- **Explain Error 提前实现，且以离线规则为主**（traceback 解析 / CUDA OOM /
  常见错误类型知识库 / 关键词兜底）。原因：它对「框选报错」这个核心场景价值最高，
  而规则实现完全离线、零依赖；LLM 只是可选增强 hook（接口已留）。
- **TranslationProvider / LLMProvider 只交付抽象，不捆绑实现**。原因：
  翻译/LLM 必然涉及联网或付费 API，违反默认 local-first；任何具体实现必须由用户
  显式配置并看到「数据将发送到 X」的提示后才允许接入。无 provider 时 action
  返回明确的降级错误，不隐藏、不静默联网。
- **Quick Actions（Ctrl+Shift+1 → 框选→OCR→复制）从 v0.5 提前**：多热键支持
  是热键线程的一次小改动，成本极低而日常价值高。
- 真实 OCR 的多行 traceback 常被合并成单行 —— Explain 解析必须用行内 search
  而非整行 match（测试 `test_merged_single_line_traceback` 锁定该行为）。

## D10. 开发控制面板：StatusWindow 而非系统托盘

**日期**: 2026-09-13

v0.1/v0.2 用一个置顶小窗口（Capture 按钮 / 热键状态 / 退出）替代系统托盘图标：
托盘需要额外依赖与更复杂的事件处理，且状态提示（如热键注册失败）更显眼；
打包为正式产品时再评估托盘化。

## D11. 热键线程：阻塞 GetMessage 而非 Peek+Sleep 轮询

**日期**: 2026-09-13（代码审查后改进）

初版用 `PeekMessageW + Sleep(30)` 轮询，热键触发最多延迟 30ms 且常驻空转。
改为阻塞 `GetMessageW`，`stop()` 用 `PostThreadMessage(WM_QUIT)` 唤醒退出：
触发零延迟、零功耗，停止语义也更直接。

## 顺序调整记录

- 2026-09-13: OCR polish（D8 CJK 规整）自 v0.2 提前 —— 属于第一阶段「OCR 结果基本正确」验收范畴。
- 2026-09-13: v0.2 完成时顺带提前了 v0.3 的 Explain/Provider 抽象与 v0.5 的 Quick Actions（理由见 D10）。
