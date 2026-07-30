# CanvasState 实现概览

## 完成内容

### 1. CanvasState 核心模块 (`autocad/canvas_state.py`)
- **数据类**: CanvasDevice / CanvasConnection / CanvasAnnotation — 轻量 dataclass
- **CanvasState 追踪器**: 纯内存存储，随会话生命周期，提供 record_*/find_*/get_summary/reset 等完整 API
- **空间智能**: 自动追踪画布边界 (min/max x/y)，提供 suggested_next_x/y 布局建议
- **会话注册表**: `get_canvas_state(session_id)` 全局单例管理

### 2. query_canvas LangChain Tool (`agent/tools/query_canvas.py`)
- 5 种查询模式: summary / devices / connections / find_space / device_detail
- LLM 通过此工具随时查询画布状态，无需"记住"任何东西
- 返回结构化 Markdown，LLM 可直接阅读

### 3. 4 个现有工具的 CanvasState 集成
- **InsertElementTool**: 插入成功后自动 record_device(handle, symbol_id, x, y, label, layer)
- **DrawConnectionTool**: 连线成功后自动 record_connection(from, to, type, layer)
- **AddAnnotationTool**: 标注后自动 record_annotation(handle, text, x, y, target)
- **ModifyElementTool**: 移动/改图层/旋转/缩放后自动 record_update_device

### 4. DrawAgent 集成 (`agent/draw_agent.py`)
- 构造函数创建 CanvasState: `self.canvas_state = get_canvas_state(session_id)`
- 5 个工具全部注入 canvas_state: `InsertElementTool(canvas_state=self.canvas_state)`
- 新增第 6 个工具 QueryCanvasTool
- clear_history() 同步重置画布状态

### 5. System Prompt 更新 (`agent/prompts/system_prompt.py`)
- 新增「画布状态查询规则」段落，指导 LLM 使用 query_canvas
- 操作流程第 2 步改为"首先调用 query_canvas"
- 强调"不应该记住画布状态，而是需要时查询"

## 架构图

```
用户: "画一个变压器 T1"
         ↓
    DrawAgent.chat_stream()
         ↓
    LLM 调用 query_canvas("summary")
         ↓
    CanvasState → "画布为空，建议从 (500,800) 开始"
         ↓
    LLM 调用 insert_element("TR_2W", x=500, y=800, label="T1")
         ↓
    Tool._run() → AutoCAD COM → 成功
         ↓
    Tool 自动调用 canvas_state.record_device(handle, "TR_2W", 500, 800, "T1")
         ↓
    CanvasState 更新: v=N+1
         ↓
    下次 LLM query_canvas → 看到 T1 已在 (500,800)
```

## 验证结果
- Python 全链路 import 通过
- CanvasState CRUD 测试通过
- 工具注入 + canvas_state 字段正常
- 后端重启成功，health check OK
- 前端 TypeScript 无新增错误
