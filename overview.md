# 电气图纸绘制机器人 - 项目概览

## 最近更新 (2026-06-03)

### P0 缺口修复

**G2: 附件按钮挂接** ✅
- InputBar 的 📎 按钮现在通过隐藏 `<input type="file">` 触发文件选择
- 支持 JPG/PNG/BMP/TIFF/WebP，最大 10MB
- 选中后显示缩略图预览 + 文件名 + 删除按钮
- 图片转 base64 随消息发送

**G1: 用户确认预览卡片** ✅
- 新增 `ConfirmCard` 组件：琥珀色警告风格卡片，显示操作摘要 + 明细列表
- 后端 `/Draw` 模式下先分析意图生成计划（`_analyze_draw_intent`）
- SSE 事件新增 `confirm_required` 类型
- 用户确认后重新发送消息执行，取消则清除计划
- `useChat` 新增 `pendingConfirm` 状态和完整确认流程

### 改动文件
- `frontend/src/components/chat/InputBar.tsx` — 附件上传功能
- `frontend/src/components/chat/ConfirmCard.tsx` — 新增确认卡片组件
- `frontend/src/components/chat/ChatPanel.tsx` — 集成 ConfirmCard
- `frontend/src/hooks/useChat.ts` — 确认状态管理
- `frontend/src/services/sseClient.ts` — onConfirmRequired 回调
- `frontend/src/types/index.ts` — SSEEvent 扩展
- `backend/api/routes/chat.py` — _analyze_draw_intent + confirm_required 事件
