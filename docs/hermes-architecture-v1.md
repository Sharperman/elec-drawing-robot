# Hermes 增强版架构设计文档 v1.0

## 1. 设计目标

基于 Hermes Agent 设计思想，构建适用于 Windows/AutoCAD 场景的轻量级 Skill 框架，实现：
- Skill 自创建与复用
- agentskills.io 开放标准兼容
- 斜杠命令统一入口
- MCP 协议桥接（未来扩展）

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              用户层                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │  聊天页面    │  │  Hermes页面  │  │  设置页面    │  │  命令输入框      │ │
│  │  (/draw)    │  │  (/hermes)  │  │  (开关配置)  │  │  (/check ...)   │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────────────────┘ │
│         └────────────────┴────────────────┴────────────────┘            │
│                                    │                                    │
│                              API 网关                                   │
│                         (FastAPI Routes)                                │
└────────────────────────────────────┼────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────┐
│                            Hermes 核心层                                 │
│                                    │                                    │
│  ┌─────────────────────────────────┴──────────────────────────────┐    │
│  │                      Skill Registry                           │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │    │
│  │  │ Internal │  │ External │  │ AutoGen  │  │   MCP Tools  │  │    │
│  │  │  Skills  │  │  Skills  │  │  Skills  │  │  (Future)    │  │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                    │                                  │
│  ┌─────────────────────────────────┴──────────────────────────────┐    │
│  │                    Skill Engine                               │    │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐  │    │
│  │  │   Loader   │  │  Executor  │  │  Auto-Creator          │  │    │
│  │  │(YAML解析)  │  │(步骤执行)  │  │  (从成功任务提取Skill)  │  │    │
│  │  └────────────┘  └────────────┘  └────────────────────────┘  │    │
│  └──────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────┐
│                            工具层                                       │
│  ┌──────────┐  ┌──────────┐  ┌─────┴──────┐  ┌──────────┐             │
│  │  CAD工具  │  │ 桌面工具  │  │  浏览器    │  │ MCP桥接  │             │
│  │ (原有6个) │  │ (截图/输入)│  │           │  │ (Phase3) │             │
│  └──────────┘  └──────────┘  └────────────┘  └──────────┘             │
└───────────────────────────────────────────────────────────────────────┘
```

## 3. 核心模块设计

### 3.1 Skill 元数据模型 (agentskills.io 兼容)

```yaml
# hermes/skills/examples/draw_3p_breaker/skill.yaml
api_version: "1.0"
spec_version: "1.0.0"

metadata:
  name: "draw_3p_breaker"
  description: "绘制三极断路器，自动标注 QF 编号"
  author: "hermes-auto-generated"
  created_at: "2026-06-09T10:00:00Z"
  updated_at: "2026-06-09T10:00:00Z"
  version: "1.0.0"
  
triggers:
  patterns:
    - "画三极断路器"
    - "绘制 3P 断路器"
    - "insert 3p breaker"
  confidence_threshold: 0.8

inputs:
  properties:
    position:
      type: "object"
      description: "插入位置"
      properties:
        x: { type: "number", default: 0 }
        y: { type: "number", default: 0 }
    label_number:
      type: "integer"
      description: "断路器编号"
      default: 1
  required: []

execution:
  type: "python"
  entry: "execute.py"
  
  # 执行步骤（可被 Auto-Creator 自动生成）
  steps:
    - tool: "insert_element"
      params:
        symbol: "breaker_3p"
        x: "${inputs.position.x}"
        y: "${inputs.position.y}"
    - tool: "annotate"
      params:
        text: "QF${inputs.label_number}"
        x: "${inputs.position.x + 10}"
        y: "${inputs.position.y - 5}"
```

### 3.2 Skill Registry 设计

```python
# hermes/skill_registry.py

class SkillRegistry:
    """
    Skill 注册表 - 管理所有可用 Skill
    
    三类 Skill:
    1. Internal Skills: 代码内置（screenshot, click, browse）
    2. External Skills: 从 skills/ 目录加载（YAML + execute.py）
    3. AutoGen Skills: 从成功任务自动生成的 Skill
    """
    
    def __init__(self, skills_dir: Path):
        self._internal: Dict[str, Skill] = {}
        self._external: Dict[str, Skill] = {}
        self._autogen: Dict[str, Skill] = {}
        self._skills_dir = skills_dir
        
    def register_internal(self, skill: Skill) -> None:
        """注册内置 Skill（截图、点击等）"""
        pass
        
    def load_external(self, skill_path: Path) -> Skill:
        """从 YAML 加载外部 Skill"""
        # 1. 解析 skill.yaml
        # 2. 验证 schema
        # 3. 返回 Skill 对象
        pass
        
    def find_matching(self, query: str) -> List[SkillMatch]:
        """根据用户输入匹配 Skill（用于斜杠命令和触发词）"""
        # 1. 匹配 triggers.patterns
        # 2. 计算 confidence
        # 3. 返回排序后的匹配列表
        pass
        
    def get_all(self) -> List[Skill]:
        """获取所有可用 Skill"""
        return list(self._internal.values()) + \
               list(self._external.values()) + \
               list(self._autogen.values())
```

### 3.3 Skill Executor 执行引擎

```python
# hermes/skill_executor.py

class SkillExecutor:
    """
    Skill 执行引擎 - 按步骤执行 Skill
    """
    
    async def execute(
        self,
        skill: Skill,
        inputs: Dict[str, Any],
        context: ExecutionContext
    ) -> ExecutionResult:
        """
        执行 Skill，返回结果
        
        Args:
            skill: 要执行的 Skill
            inputs: 输入参数
            context: 执行上下文（用户ID、会话ID等）
            
        Returns:
            ExecutionResult: 包含 success, output, logs, execution_time
        """
        results = []
        
        for step in skill.steps:
            # 1. 解析参数模板（${inputs.x} → 实际值）
            params = self._resolve_templates(step.params, inputs)
            
            # 2. 获取工具
            tool = self._get_tool(step.tool)
            
            # 3. 执行
            result = await tool.run(**params)
            results.append(result)
            
            # 4. 中断检查
            if context.interrupted:
                break
                
        return ExecutionResult(
            success=all(r.success for r in results),
            outputs=[r.output for r in results],
            logs=self._format_logs(results)
        )
```

### 3.4 Auto-Creator 自创建机制

```python
# hermes/auto_creator.py

class SkillAutoCreator:
    """
    Skill 自动创建器 - 从成功任务提取可复用 Skill
    
    触发条件:
    1. Agent 完成任务（success）
    2. 任务步骤数 >= 2（有意义）
    3. 用户明确说"保存为 Skill"或自动检测高价值任务
    """
    
    async def create_from_execution(
        self,
        task_description: str,
        execution_trace: ExecutionTrace,
        llm_client: LLMClient
    ) -> Optional[Skill]:
        """
        从执行轨迹创建 Skill
        
        流程:
        1. 提取执行步骤（工具调用序列）
        2. LLM 生成 Skill 元数据（名称、描述、触发词）
        3. 生成 skill.yaml
        4. 生成 execute.py（或直接用步骤配置）
        5. 保存到 skills/autogen/
        """
        # 示例执行轨迹:
        # [
        #   {"tool": "insert_element", "params": {...}, "result": {...}},
        #   {"tool": "annotate", "params": {...}, "result": {...}}
        # ]
        
        # LLM Prompt:
        # "从以下成功任务提取可复用 Skill...
        #  任务: 画三极断路器
        #  步骤: [JSON轨迹]
        #  请生成 Skill YAML 配置"
        pass
```

## 4. 数据模型

### 4.1 Skill 表（SQLite）

```sql
CREATE TABLE hermes_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id TEXT UNIQUE NOT NULL,      -- 唯一标识符 (如 "draw_3p_breaker")
    name TEXT NOT NULL,                  -- 显示名称
    description TEXT,                    -- 描述
    
    -- 分类
    category TEXT,                       -- "internal" | "external" | "autogen"
    source TEXT,                         -- 来源路径或"builtin"
    
    -- 触发配置（JSON）
    triggers TEXT,                       -- JSON {"patterns": [...], "threshold": 0.8}
    
    -- 执行配置（JSON）
    execution_config TEXT,               -- YAML 配置 JSON 化存储
    
    -- 统计
    use_count INTEGER DEFAULT 0,
    success_rate REAL DEFAULT 1.0,
    last_used_at TIMESTAMP,
    
    -- 元数据
    created_by TEXT,                     -- "system" | "user" | "auto"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 状态
    is_active BOOLEAN DEFAULT 1,
    is_deleted BOOLEAN DEFAULT 0
);

-- 索引
CREATE INDEX idx_skills_category ON hermes_skills(category);
CREATE INDEX idx_skills_active ON hermes_skills(is_active);
```

### 4.2 SkillExecution 表（执行记录）

```sql
CREATE TABLE hermes_skill_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT UNIQUE NOT NULL,   -- UUID
    skill_id TEXT NOT NULL,
    session_id TEXT,                     -- 关联 chat session
    
    -- 输入输出
    inputs TEXT,                         -- JSON
    outputs TEXT,                        -- JSON
    
    -- 执行详情
    steps TEXT,                          -- JSON 步骤执行详情
    logs TEXT,                           -- 执行日志
    
    -- 结果
    success BOOLEAN,
    error_message TEXT,
    execution_time_ms INTEGER,
    
    -- 时间戳
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    
    FOREIGN KEY (skill_id) REFERENCES hermes_skills(skill_id)
);
```

## 5. API 设计

### 5.1 Skill 管理 API

```python
# GET /api/hermes/skills
# 列出所有 Skill（支持筛选）
{
  "code": 0,
  "data": {
    "skills": [
      {
        "id": "desktop_screenshot",
        "name": "截图",
        "category": "internal",
        "description": "截取屏幕或指定窗口",
        "use_count": 45
      },
      {
        "id": "draw_3p_breaker",
        "name": "画三极断路器",
        "category": "autogen",
        "description": "自动绘制三极断路器并标注",
        "use_count": 12
      }
    ]
  }
}

# POST /api/hermes/skills/{skill_id}/execute
# 执行 Skill
{
  "inputs": {
    "position": {"x": 100, "y": 200},
    "label_number": 1
  }
}

# Response (SSE 流)
event: step_start
data: {"step": 1, "tool": "insert_element", "status": "running"}

event: step_complete
data: {"step": 1, "status": "success", "result": {...}}

event: complete
data: {"success": true, "execution_time_ms": 1250}

# DELETE /api/hermes/skills/{skill_id}
# 删除 Skill（仅 external/autogen）

# POST /api/hermes/skills/{skill_id}/enable|disable
# 启用/禁用 Skill
```

### 5.2 命令解析 API

```python
# POST /api/hermes/parse-command
# 解析用户输入的命令
{
  "text": "/draw 断路器QF01 在坐标 100,200"
}

# Response
{
  "code": 0,
  "data": {
    "is_command": true,
    "command": "/draw",
    "skill_id": "draw_element",  # 匹配的 Skill
    "parsed_inputs": {
      "element": "断路器",
      "label": "QF01",
      "position": {"x": 100, "y": 200}
    },
    "suggestions": []  # 如果不匹配，返回建议命令
  }
}
```

### 5.3 Auto-Creator API

```python
# POST /api/hermes/skills/autocreate
# 手动触发 Skill 创建（从最近的成功任务）
{
  "session_id": "chat_123",
  "task_description": "画三极断路器"
}

# Response
{
  "code": 0,
  "data": {
    "skill_id": "draw_3p_breaker_abc123",
    "name": "画三极断路器",
    "confidence": 0.95,
    "preview": {
      "steps": [...],
      "yaml_preview": "..."
    }
  }
}

# POST /api/hermes/skills/autocreate/confirm
# 确认保存自动创建的 Skill
{
  "skill_id": "draw_3p_breaker_abc123",
  "confirmed": true
}
```

## 6. 前端设计

### 6.1 Hermes 页面布局

```
┌─────────────────────────────────────────────────────────────┐
│  Hermes Skill 管理                                  [+]新建 │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────┐  ┌──────────────────────────────┐ │
│  │  📁 分类筛选          │  │  Skill 详情                  │ │
│  │  ○ 全部 (15)         │  │                              │ │
│  │  ● 内置 (4)          │  │  [desktop_screenshot]        │ │
│  │  ○ 外部 (3)          │  │                              │ │
│  │  ○ 自动生成 (8)      │  │  截图工具                     │ │
│  │                      │  │  截取屏幕或指定窗口            │ │
│  │  ─────────────       │  │                              │ │
│  │  🔍 搜索 Skill...    │  │  触发词: 截图, 截屏, capture │ │
│  │                      │  │                              │ │
│  │  ─────────────       │  │  使用次数: 45                │ │
│  │  📊 统计             │  │  成功率: 98%                 │ │
│  │  总执行: 128         │  │                              │ │
│  │  成功率: 96%         │  │  [测试] [编辑] [禁用] [删除] │ │
│  └──────────────────────┘  └──────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  🔄 最近自动生成的 Skill                                    │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ 画三极断路器 │ │ 查询电缆规范 │ │ 导出PDF图纸 │           │
│  │ ✓ 已启用    │ │ ⏳ 待审核    │ │ ✓ 已启用    │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 聊天页面命令输入

```
用户输入: /
          ↓
弹出命令菜单:
┌──────────────────────────────────┐
│ /draw      绘制电气图元          │
│ /check     图纸合规性检查        │
│ /browse    浏览网页查资料        │
│ /hermes    桌面操作 (CU模式)     │
│ /learn     学习参考图纸模式      │
└──────────────────────────────────┘

用户选择 /draw 后:
输入框变为: /draw 
提示参数: [图元类型] [位置] [标注]
```

## 7. 开发计划

### Phase 1: Skill 系统核心 (2-3 天)

| 序号 | 任务 | 输出文件 |
|-----|------|---------|
| 1.1 | Skill 元数据模型定义 | `hermes/models/skill.py` |
| 1.2 | YAML 解析器 | `hermes/parsers/yaml_loader.py` |
| 1.3 | Skill Registry 实现 | `hermes/skill_registry.py` |
| 1.4 | Skill Executor 引擎 | `hermes/skill_executor.py` |
| 1.5 | Auto-Creator 自创建 | `hermes/auto_creator.py` |
| 1.6 | 数据表迁移 | `alembic/versions/xxx_hermes_skills.py` |
| 1.7 | API 路由实现 | `hermes/router.py` |
| 1.8 | 前端 Hermes 页面 | `components/config/HermesPage.tsx` |

### Phase 2: 斜杠命令系统 (1 天)

| 序号 | 任务 | 输出文件 |
|-----|------|---------|
| 2.1 | 命令解析器 | `hermes/command_parser.py` |
| 2.2 | 后端命令路由 | `api/routes/commands.py` |
| 2.3 | 前端命令提示 UI | `components/chat/CommandInput.tsx` |
| 2.4 | 与 DrawAgent 集成 | `agent/draw_agent.py` (修改) |

### Phase 3: MCP 桥接 (1-2 天，可选)

| 序号 | 任务 | 输出文件 |
|-----|------|---------|
| 3.1 | MCP Client 实现 | `hermes/mcp/client.py` |
| 3.2 | Tool 桥接层 | `hermes/mcp/tool_bridge.py` |
| 3.3 | MCP Server 管理 | `hermes/mcp/server_manager.py` |

## 8. 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|-----|-----|------|---------|
| YAML 配置复杂度过高 | 中 | 中 | 提供可视化编辑器 |
| Auto-Creator 生成质量低 | 高 | 中 | 人工确认环节 + 置信度阈值 |
| 与现有工具冲突 | 低 | 高 | 完整回归测试 |
| 性能问题（大量 Skill） | 中 | 低 | 缓存 + 索引优化 |

## 9. 验收标准

- [ ] 可以从 YAML 加载并执行 Skill
- [ ] 成功任务可自动提取为 Skill（人工确认）
- [ ] 斜杠命令 `/draw`, `/check`, `/browse` 正常工作
- [ ] Skill 可在 Hermes 页面管理（CRUD）
- [ ] 与现有 DrawAgent 无缝集成
- [ ] 不影响非 CU 模式下的任何功能

---

**文档版本**: v1.0  
**作者**: Senior Developer  
**日期**: 2026-06-09
