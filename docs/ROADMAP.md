# Screen Command Roadmap

长期方向（来自产品定义），按版本推进。每完成一版在本文档更新状态。

## v0.1 — Phase 1（已完成 2026-09-13）
核心验收：**框一下 → OCR 出结果**，整条链稳定。

- [x] Capture Core：屏幕抓取 / 区域裁剪，内存 buffer，不落盘
- [x] Selection Overlay：暗色蒙层 / 拖拽 / 尺寸提示 / Esc 取消 / 重新框选
- [x] 多显示器 + DPI 缩放正确性
- [x] OCRProvider 抽象 + Windows 内置 OCR（en + zh）+ Mock provider
- [x] Action 抽象 + OCRAction
- [x] Action Menu（浮窗）
- [x] Result Window：选中 / 复制 / 重试 / 关闭
- [x] Save Screenshot（显式动作才写文件）
- [x] Copy Text Action
- [x] CLI test harness：`process <image> --action ocr`
- [x] 测试：英文 / 中文 / 混合 / 终端输出 / 代码 / 报错 / 小字 / 深底 / 浅底
- [x] 边界：取消框选 / 零尺寸 / 极小区域 / 大区域 / 屏幕边缘 / DPI
- [x] 全局快捷键（运行期临时注册，无持久修改）

## v0.2（2026-09-13 完成）
- [x] Translate —— provider abstraction 就绪；**未捆绑任何实现**（隐私 + 不强依赖付费 API），
      无 provider 时优雅降级并明确提示
- [x] Markdown 输出 action（段落/代码块组装，离线规则）
- [x] Code OCR（全角/智能标点修复、行号剥离、缩进保留、语言猜测，离线规则）
- [x] Action keyboard shortcuts（菜单数字键 1–7）
- [x] Explain Error（提前自 v0.3：离线规则分析可用，LLM 仅是可选增强 hook）
- [x] LLMProvider / TranslationProvider 抽象（提前自 v0.3 的 provider abstraction 部分）
- [x] Quick Actions（提前自 v0.5：`Ctrl+Shift+1` = 框选→OCR→复制，多热键支持）

## v0.3（剩余部分）
- [ ] LLM provider 具体实现（用户显式配置后接入；无则保持优雅降级）
- [ ] Provider 超时 / 重试 / 取消
- [ ] Translate 的首个具体 provider 实现

## v0.4
- [ ] Formula → LaTeX（接口 + UI 先行）
- [ ] Table → Markdown / CSV / JSON

## v0.5（剩余部分）
- [ ] History（optional，默认考虑隐私）
- [ ] 历史搜索

## v0.6
- [ ] Smart Action Suggestion（简单规则，不搞模型分类）
- [ ] Content Detection（text/code/formula/table/error + confidence）

## v0.7
- [ ] Custom Actions（yaml 配置）
- [ ] Local Scripts（安全边界明确）

## v0.8
- [ ] macOS / Linux 移植评估

## 明确不做（MVP 及可预见未来）
Agent / 自动控制电脑 / 浏览器插件 / 完整截图编辑器 / 云账号 / 同步 /
团队协作 / 插件市场 / 自动执行命令 / 复杂工作流编辑器。
