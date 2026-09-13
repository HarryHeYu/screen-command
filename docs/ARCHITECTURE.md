# 架构

## 总览

```
┌────────────────────────────── UI 层 (Qt) ──────────────────────────────┐
│  OverlayWindow(per-screen)   ActionMenu(浮窗)   ResultWindow   StatusWindow │
└──────────────┬──────────────────────────────────────────┬──────────────┘
               │                                          │
┌──────────────▼───────────────────────┐   ┌──────────────▼──────────────┐
│            AppController             │   │        Action 层             │
│  状态机: Idle/Capturing/Choosing/    │──▶│  Action(ABC): id/name/...   │
│  Processing/ShowingResult            │   │   execute(CaptureContext)   │
└──────────────┬───────────────────────┘   │  → ActionResult(结构化)     │
               │                            └──────────────┬──────────────┘
┌──────────────▼───────────────────────┐                  │
│            Core 能力层                │                  │
│  capture: snapshot / crop (内存)      │   ┌──────────────▼──────────────┐
│  hotkey:  RegisterHotKey 线程         │   │         Provider 层          │
│  clipboard / filesave                 │   │  OCRProvider(ABC)            │
└──────────────────────────────────────┘   │   ├ WindowsOcrProvider       │
                                           │   └ MockOcrProvider          │
                                           └──────────────────────────────┘
```

原则：**UI 不直接依赖具体 provider 实现**；action 通过 provider 接口取能力；
core 能力（capture 等）与 UI 解耦，可被 CLI harness 复用。

## 关键数据流

### 框选 → OCR

```
hotkey/按钮触发
→ CaptureEngine.snapshot_all_screens()     # 每屏 QPixmap，冻结画面
→ 每屏显示 OverlayWindow(背景=快照+蒙层)
→ 用户拖拽 → 松开
→ CaptureEngine.crop(snapshot, region)     # 物理像素裁剪 → 内存 PNG bytes
→ ActionMenu 弹出（不等待 OCR）
→ 用户选 OCR → OCRAction.execute(ActionContext) -> ActionResult
→ OCRProvider.recognize() (后台线程)
→ ActionResult(text=...)
→ ResultWindow 显示
```

### CLI harness（无屏幕）

```
screen_command process img.png --action ocr
→ 读文件 → OCRAction → provider → 打印/保存结果
```

## 模块约定

| 模块 | 职责 | 禁止 |
|---|---|---|
| `capture.py` | 全屏快照、区域裁剪、物理像素输出 | 写临时文件 |
| `overlay.py` | 选区交互 | 调 provider |
| `ocr/base.py` | `OCRProvider` ABC、`OcrResult` | import 具体实现 |
| `actions/base.py` | `Action` ABC、注册表、`ActionResult` | import UI |
| `ui/*` | 展示 | 直接 import winrt |

## ActionResult 结构化

```python
ActionResult:
  action_id: str
  ok: bool
  text: str            # 纯文本视图
  markdown: str|None   # 富文本视图
  data: dict           # action 特有（如 table 的 csv）
  error: str|None
  elapsed_ms: float
```

UI 只消费 `text/markdown`，复制/保存按 type 分发 —— 不允许 action 往 UI 塞裸字符串了事。

## 线程模型

- Qt 主线程：所有 UI。
- OCR / 未来网络 action：`QThreadPool` / worker 线程，结果经 signal 回主线程；协作式取消为 v0.3 计划（cancel_token 已预留，当前恒为 None）。
- 热键：独立 Win32 线程（消息循环），触发后经 Qt Signal 桥（queued connection）回主线程。

## DPI 与多显示器

- 进程 per-monitor DPI aware（Qt6 默认）。
- 每个物理屏一个 OverlayWindow，窗口 geometry = 该屏 availGeometry，
  内部把屏幕逻辑坐标 ↔ 快照物理像素转换封装在 `ScreenMapping`。
- 选区统一以**全局逻辑坐标**表示，裁剪时换算到目标屏物理像素。
