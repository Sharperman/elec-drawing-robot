# PRD 差距分析报告

**分析日期**：2026-06-03  
**PRD 版本**：v1.0 (2025-05-21)  
**分析范围**：P0（MVP）和 P1（第一个完整版本）全部需求  
**分析人**：Senior Developer (高级开发工程师)

---

## 总览

| 优先级 | 总数 | 已实现 | 部分实现 | 未实现 |
|--------|------|--------|----------|--------|
| P0 | 6 | 5 | 1 | 0 |
| P1 | 6 | 1 | 1 | 4 |
| **合计** | **12** | **6** | **2** | **4** |

---

## P0 — MVP 范围（6 项）

### ✅ P0-01：AutoCAD COM/ActiveX 接口集成
**状态**：✅ **已实现**

- `backend/autocad/connection.py`：COM 连接管理（单例、心跳检测、自动重连）
- `backend/autocad/drawing_ops.py`：图元插入/删除/移动/连线、简易符号降级绘制
- `backend/autocad/annotation_ops.py`：文字标注和尺寸标注
- `backend/autocad/layer_manager.py`：图层管理
- `backend/autocad/transaction.py`：事务封装（支持回滚）
- `backend/autocad/retry.py`：指数退避重试装饰器
- `backend/autocad/snapshot.py`：图纸截图
- 非功能性需求中的"3 次重试"已实现 ✅

### ✅ P0-02：内置电气图元符号库
**状态**：✅ **已实现**

- `backend/knowledge/data/symbols/symbols.json`：16 个 GB/T 4728 基础图元
- `backend/knowledge/symbol_library.py`：图元 CRUD 管理
- `backend/autocad/drawing_ops.py`：`create_simple_symbol()` 当图块不存在时用基础图元绘制（矩形/圆/线+文字）
- 前端 `SymbolLibrary.tsx`：符号库浏览/管理界面
- 覆盖 PRD 要求的：断路器、隔离开关、变压器、母线、接地、避雷器、互感器、开关柜 ✅

### ✅ P0-03：文字输入交互界面
**状态**：✅ **已实现**

- `ChatPanel.tsx` + `MessageList.tsx` + `MessageItem.tsx` + `InputBar.tsx`：完整对话界面
- LangChain Agent 解析自然语言 → 调用 AutoCAD 工具执行
- SSE 流式响应：`chat_stream()` 方法
- 三种运行模式：Auto / Check / Draw
- 快捷指令面板：`QuickCommandPanel.tsx`
- 消息持久化到 SQLite，刷新后从后端加载

### ✅ P0-04：图片/图纸上传识别
**状态**：✅ **已实现**

- `FileUpload.tsx`：拖拽上传，支持 JPG/PNG/BMP/TIFF/WebP，最大 10MB
- `useImageUpload.ts`：base64 转换 + API 调用
- `POST /api/recognize`：接收图片 → YOLOv8 推理（或规则降级）→ 结构化结果
- 识别结果包含：图元名称、位置、置信度
- 前端可展示识别结果列表

### ⚠️ P0-05：绘图规范配置
**状态**：⚠️ **部分实现**

已实现：
- ✅ 规范模板 CRUD（创建/编辑/删除/激活）
- ✅ 图层映射表配置（颜色/线型/线宽）
- ✅ 图框配置（`default_standard.json` 含 `frame_block_name`）
- ✅ 规范通过 RAG 注入到 Agent 提示词

**未完全实现：**
- ❌ **字体配置**：架构文档定义的 `font_config`（字高、字体名）在 `default_standard.json` 中有定义，但前端 StandardsConfig 页面缺少字体配置编辑界面
- ❌ **线型配置**：`line_type_config` 同理，前端 LayerMapping 只有颜色/线型/线宽的基础编辑，缺少全局线型库管理
- ❌ **用户偏好记录页**：PRD 6.3 节明确要求"用户偏好记录（已学习的修改意见列表，可启用/禁用/删除）"——后端 feedback 模块已实现，但前端没有对应的管理页面

### ✅ P0-06：基础错误提示
**状态**：✅ **已实现**

- `backend/utils/error_codes.py`：完整错误码体系（1001~9999）
- `backend/api/middleware.py`：全局异常处理
- `DrawAgent._fallback_response()`：LLM 不可用时的降级回复
- 前端 `ErrorBoundary.tsx`：防止白屏
- Toast 通知：操作成功/失败提示
- SSE 事件中的 `error` 类型事件

---

## P1 — 第一个完整版本（6 项）

### ❌ P1-01：语音输入交互
**状态**：❌ **未实现**

- 代码库中无任何 `whisper`、`voice`、`speech`、`ASR` 相关代码
- 前端 `InputBar.tsx` 无麦克风按钮（PRD 布局草图中有 🎤 按钮）
- 架构文档预留了 `faster-whisper` 依赖，但注释掉了
- 架构文档明确："MVP 阶段不实现"——确认 P1 延期

### ⚠️ P1-02：修改意见学习
**状态**：⚠️ **部分实现**

已实现：
- ✅ `backend/feedback/collector.py`：接收用户反馈，持久化到 SQLite
- ✅ `backend/feedback/refiner.py`：LLM 驱动反馈→规则提炼
- ✅ `backend/feedback/injector.py`：规则注入到 Agent 提示词
- ✅ `POST /api/feedback` 和 `GET /api/feedback/rules` 路由

**未完全实现：**
- ❌ **前端无反馈提交 UI**：用户在对话界面没有"满意/不满意"按钮或修改意见输入框
- ❌ **前端无学习规则管理页**：PRD 6.3 节要求"用户偏好记录（已学习的修改意见列表，可启用/禁用/删除）"，后端 API 已就绪但前端无页面

### ❌ P1-03：厂家资料解析
**状态**：❌ **未实现**

- 代码库中无任何 PDF 解析、设备参数提取、材料表生成相关代码
- 无"导入厂家资料"的前端界面

### ✅ P1-04：多轮对话上下文保持
**状态**：✅ **已实现**

- `DrawAgent._message_history`：保留最近 20 条消息
- `backend/agent/context_manager.py`：绘图上下文管理（图元注册、意图历史）
- `context_manager.get_context_summary()`：生成上下文摘要
- SSE 流式对话自动更新历史
- 消息持久化到 `chat_messages` 表

### ❌ P1-05：规范校验与提示
**状态**：❌ **未实现**

- `backend/knowledge/electrical_standards.py`：已定义审查规则清单（~20 条），但仅用于 `check` 模式的图纸审查
- 缺少 PRD 描述的"出图完成后自动比对规范库，高亮不合规处并给出修改建议"的**主动校验流程**
- 当前的审查模式需要用户主动切换到 `/Check` 模式，而非自动触发
- 缺少"不合规高亮"的可视化呈现

### ❌ P1-06：典型图纸模板库
**状态**：❌ **未实现**

- 无"强电/弱电系统图、平面布置图、接线图"的预置模板
- 无模板浏览/选择/应用界面
- `default_standard.json` 只有规范配置，不是图纸模板

---

## PRD 交互流程验证

### 流程 A：文字指令绘图
| 步骤 | PRD 描述 | 实现状态 |
|------|----------|----------|
| 1. 用户输入绘图需求 → 发送 | ✅ | InputBar + handleSend |
| 2. 系统回显解析结果 | ✅ | SSE thinking/tool_start 事件 |
| 3. 用户确认 → 执行 | ⚠️ | `POST /api/chat/confirm` 路由存在，但前端 `confirmPlan()` 没有被 UI 调用——缺少"确认预览卡片" |
| 4. AutoCAD 预览区刷新 | ✅ | AutoCADPreview 轮询截图 |

**缺口**：PRD 描述的"系统回显解析结果 → 用户确认 → 执行"三步流程中，**用户确认环节**的前端 UI 不完整。后端有 `/confirm` 端点，前端 `useChat` 有 `confirmPlan` 方法，但 ChatPanel 中没有渲染确认卡片。

### 流程 B：图片上传识别
| 步骤 | PRD 描述 | 实现状态 |
|------|----------|----------|
| 1. 用户上传图片 | ✅ | FileUpload + useDropzone |
| 2. 系统返回识别结果列表 | ✅ | YOLOv8 / 规则降级 |
| 3. 用户点击图元查看详情 | ⚠️ | 识别结果返回了，但前端 MessageItem 对识别结果的渲染需要验证 |
| 4. "以此为基础继续绘制" | ❌ | 无此交互逻辑——识别结果未存入会话上下文供后续引用 |

**缺口**：PRD 描述的"点击某图元查看详情，或指令'以此为基础继续绘制'"的交互链路不完整。

### 流程 C：语音输入
| 步骤 | PRD 描述 | 实现状态 |
|------|----------|----------|
| 全部 | — | ❌ 未实现（P1-01） |

---

## PRD UI 布局验证

| PRD UI 元素 | 实现状态 |
|-------------|----------|
| Logo + 应用标题 | ✅ AppShell 中有品牌标识 |
| 项目列表下拉 | ✅ Sidebar 会话列表 |
| 设置按钮 | ✅ 路由到 /settings |
| 帮助按钮 | ❌ 无帮助页面/按钮 |
| AutoCAD 预览区 | ✅ AutoCADPreview（默认折叠） |
| 对话交互区 | ✅ ChatPanel |
| 输入框 | ✅ InputBar |
| 🎤 语音按钮 | ❌ 未实现（P1-01） |
| 📎 附件按钮 | ⚠️ 按钮存在但点击无动作（未连接到 FileUpload） |
| 发送按钮 | ✅ |
| 状态栏（AutoCAD 连接状态 + 图纸名） | ✅ StatusBar |

---

## 关键缺口汇总（按优先级）

### 🔴 P0 级缺口

| # | 缺口 | 影响 |
|---|------|------|
| G1 | **用户确认预览卡片缺失** | PRD 流程 A 要求"系统回显解析结果 → 用户确认 → 执行"，后端 `/confirm` 就绪但前端无确认 UI。对高风险操作（如删除图元、批量修改）缺乏保护 |
| G2 | **附件按钮未挂接** | InputBar 中 📎 按钮点击无动作，未连接到 FileUpload 组件，图片上传功能实际不可用 |

### 🟡 P1 级缺口

| # | 缺口 | 影响 |
|---|------|------|
| G3 | **语音输入完全未实现** | P1-01 整项缺失，前端无麦克风按钮，后端无 ASR 集成 |
| G4 | **厂家资料解析未实现** | P1-03 整项缺失，无 PDF 解析、设备参数提取、材料表生成 |
| G5 | **自动规范校验未实现** | P1-05 缺失，仅在 /Check 模式下人工触发，非"出图完成后自动比对" |
| G6 | **图纸模板库未实现** | P1-06 缺失，无强电/弱电系统图、平面布置图、接线图模板 |
| G7 | **反馈 UI 缺失** | 后端反馈学习系统完整，但前端无"满意/不满意"按钮、无学习规则管理页 |
| G8 | **字体/线型全局配置页缺失** | P0-05 部分实现，规范配置页缺少字体和线型的全局管理 |

### 🟢 建议优化

| # | 建议 |
|---|------|
| S1 | "以此为基础继续绘制"交互链路（识别结果 → 会话上下文 → 绘图指令） |
| S2 | 帮助页面/按钮 |
| S3 | 识别结果在 MessageItem 中的富文本渲染（图元卡片列表） |

---

## 结论

**整体完成度**：P0 需求 5/6 完全实现（83%），P1 需求 1/6 完全实现（17%）。

代码库的文件层面 100% 覆盖了架构设计，核心架构（Agent、AutoCAD COM、YOLOv8、RAG、反馈学习）均已生产级实现。但 **PRD 中部分交互流程和 P1 功能存在缺口**，主要集中在：

1. **前端交互完整性**（确认流程、附件挂接、反馈 UI）
2. **P1 整项缺失**（语音、厂家资料解析、自动规范校验、图纸模板）
3. **UI 细节**（帮助按钮、字体配置页）

**建议优先修复**：G1（确认预览卡片）和 G2（附件按钮挂接），这两个直接影响 P0 核心用户故事的完整闭环。
