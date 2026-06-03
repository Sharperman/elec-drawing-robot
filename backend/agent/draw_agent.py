"""
LangChain Agent 初始化
AgentExecutor + 5 个 Tool + Memory + 规范上下文注入
"""
import json
from typing import Optional, AsyncIterator

from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from loguru import logger


class DrawAgent:
    """
    电气图纸绘制 Agent
    
    基于 LangChain OpenAI Tools Agent，集成 5 个工具：
    - InsertElement：插入图元
    - DrawConnection：绘制连线
    - AddAnnotation：添加标注
    - ModifyElement：修改图元
    - QueryDrawing：查询图纸
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._executor: Optional[AgentExecutor] = None
        self._message_history: list[BaseMessage] = []

    def _build_executor(self, standards_context: str = "", learned_rules: Optional[list[str]] = None, acad_connected: bool = False, drawing_name: str = "") -> AgentExecutor:
        """
        构建 AgentExecutor（每次调用时动态构建以注入最新规范）

        Args:
            standards_context: 从 RAG 检索的规范上下文
            learned_rules: 学习规则列表
            acad_connected: AutoCAD 是否已连接
            drawing_name: 当前图纸名称

        Returns:
            AgentExecutor 实例
        """
        from config import settings
        from agent.prompts.system_prompt import build_system_prompt
        from agent.tools.insert_element import InsertElementTool
        from agent.tools.draw_connection import DrawConnectionTool
        from agent.tools.add_annotation import AddAnnotationTool
        from agent.tools.modify_element import ModifyElementTool
        from agent.tools.query_drawing import QueryDrawingTool

        # LLM
        llm = ChatOpenAI(
            model=settings.MODEL_NAME,
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.OPENAI_BASE_URL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            streaming=True,
        )

        # 工具集
        tools = [
            InsertElementTool(),
            DrawConnectionTool(),
            AddAnnotationTool(),
            ModifyElementTool(),
            QueryDrawingTool(),
        ]

        # 系统提示词（含规范上下文 + AutoCAD 连接状态）
        system_prompt = build_system_prompt(
            standards_context=standards_context,
            learned_rules=learned_rules,
            acad_connected=acad_connected,
            drawing_name=drawing_name,
        )

        # Prompt 模板
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # 创建 Agent
        agent = create_openai_tools_agent(llm=llm, tools=tools, prompt=prompt)

        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=settings.AGENT_VERBOSE,
            max_iterations=settings.AGENT_MAX_ITERATIONS,
            return_intermediate_steps=True,
            handle_parsing_errors=True,
        )

        return executor

    async def chat(
        self,
        user_input: str,
        image_data: Optional[str] = None,
        standards_context: str = "",
        learned_rules: Optional[list[str]] = None,
        acad_connected: bool = False,
        drawing_name: str = "",
        mode: str = "auto",
    ) -> str:
        """
        单轮对话（非流式）

        Args:
            user_input: 用户输入
            image_data: 附带图片 base64
            standards_context: 规范上下文
            learned_rules: 学习规则
            acad_connected: AutoCAD 连接状态
            drawing_name: 当前图纸名称

        Returns:
            Agent 回复字符串
        """
        mode_instruction = self._build_mode_instruction(mode)
        executor = self._build_executor(standards_context, learned_rules, acad_connected, drawing_name)

        # 构建输入
        agent_input: dict = {
            "input": user_input,
            "chat_history": self._message_history[-20:],  # 保留最近 20 条
        }

        effective_input = mode_instruction + "\n\n" + user_input
        agent_input["input"] = effective_input

        try:
            result = await executor.ainvoke(agent_input)
            output = str(result.get("output", ""))

            # 更新消息历史
            self._message_history.append(HumanMessage(content=user_input))
            self._message_history.append(AIMessage(content=output))

            return output

        except Exception as e:
            logger.error(f"DrawAgent.chat failed for session {self.session_id}: {e}")
            # Fallback 回复
            return self._fallback_response(user_input, str(e))

    async def chat_stream(
        self,
        user_input: str,
        image_data: Optional[str] = None,
        standards_context: str = "",
        learned_rules: Optional[list[str]] = None,
        acad_connected: bool = False,
        drawing_name: str = "",
        mode: str = "auto",
    ) -> AsyncIterator[dict]:
        """
        流式对话（生成结构化 SSE 事件）

        Args:
            mode: 运行模式
                - "auto": 自动模式，根据输入判断
                - "check": 图纸审查模式，优先 DXF 文本解析 → 视觉 → COM
                - "draw": 绘图模式，优先 COM 模式

        Yields:
            dict 事件，格式：
            - {"type": "thinking", "content": "正在分析图纸..."}
            - {"type": "tool_start", "tool_name": "xxx", "tool_input": "..."}
            - {"type": "tool_end", "tool_name": "xxx", "tool_output": "..."}
            - {"type": "text", "content": "token..."}
            - {"type": "done"}
            - {"type": "error", "content": "..."}
        """
        from config import settings
        from agent.tools import (
            InsertElementTool, DrawConnectionTool,
            AddAnnotationTool, ModifyElementTool, QueryDrawingTool,
        )
        from agent.prompts.system_prompt import build_system_prompt

        # 构建系统提示词（含模式特定指令）
        mode_instruction = self._build_mode_instruction(mode)
        system_prompt = build_system_prompt(standards_context, learned_rules, acad_connected, drawing_name)
        system_prompt = mode_instruction + "\n\n" + system_prompt

        llm = ChatOpenAI(
            model=settings.MODEL_NAME,
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.OPENAI_BASE_URL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            streaming=True,
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        tools = [
            InsertElementTool(),
            DrawConnectionTool(),
            AddAnnotationTool(),
            ModifyElementTool(),
            QueryDrawingTool(),
        ]

        agent = create_openai_tools_agent(llm=llm, tools=tools, prompt=prompt)
        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=settings.AGENT_VERBOSE,
            max_iterations=settings.AGENT_MAX_ITERATIONS,
            return_intermediate_steps=False,
            handle_parsing_errors=True,
        )

        full_output = ""
        try:
            # 通知前端开始思考
            yield {"type": "thinking", "content": "正在分析您的需求..."}

            async for event in executor.astream_events(
                {
                    "input": user_input,
                    "chat_history": self._message_history[-20:],
                },
                version="v2",
            ):
                kind = event["event"]
                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, "content") and chunk.content:
                        token = chunk.content
                        full_output += token
                        yield {"type": "text", "content": token}
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_input = event["data"].get("input", {})
                    # 序列化 tool_input（可能是 dict 或其他类型）
                    try:
                        tool_input_str = json.dumps(tool_input, ensure_ascii=False, default=str)
                    except Exception:
                        tool_input_str = str(tool_input)
                    yield {
                        "type": "tool_start",
                        "tool_name": tool_name,
                        "tool_input": tool_input_str[:500],
                    }
                elif kind == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    tool_output = event["data"].get("output", "")
                    yield {
                        "type": "tool_end",
                        "tool_name": tool_name,
                        "tool_output": str(tool_output)[:500],
                    }

            # 更新历史
            self._message_history.append(HumanMessage(content=user_input))
            self._message_history.append(AIMessage(content=full_output))

            yield {"type": "done"}

        except Exception as e:
            logger.error(f"DrawAgent.chat_stream failed: {e}")
            yield {"type": "error", "content": str(e)[:500]}

    def clear_history(self) -> None:
        """清除对话历史"""
        self._message_history.clear()

    @staticmethod
    def _build_mode_instruction(mode: str) -> str:
        """
        根据运行模式构建特定的系统指令

        Args:
            mode: "auto" | "check" | "draw"

        Returns:
            模式指令字符串（追加到 system prompt 之前）
        """
        if mode == "check":
            return """【当前模式：图纸审查模式 /Check】

你是电气图纸审查专家。请严格按照以下流程进行图纸审查：

## 审查流程
1. **读取图纸**：优先使用 DXF 文本解析工具读取图纸的结构化文本标注（设备编号、文字说明等）；如 DXF 不可用，使用视觉模式截图分析；最次使用 COM 模式查询图元。
2. **逐项审查**：结合电气规范知识库中的审查清单，逐项检查图纸的完整性、规范性、一致性和安全性。
3. **先出摘要，再出 JSON**：先用简短文字概述审查结果（200字以内），然后输出完整的 JSON 审查报告。

## JSON 输出规范（非常重要）
- 在回答的最后，用 ```json 代码块输出完整的审查结果 JSON
- **JSON 必须语法完整**：确保所有花括号闭合，所有字符串用双引号
- **保持简洁**：detail 字段控制在 50 字以内，suggestion 控制在 60 字以内
- **优先输出核心检查项**（安全性 > 完整性 > 一致性 > 规范性），次要项可以合并
- checks 数组控制在 10-15 条以内，不要逐条列出所有审查规则

JSON 格式：
```json
{{
  "drawing_info": {{
    "drawing_name": "图纸名称",
    "drawing_type": "图纸类型",
    "project_name": "项目名称",
    "voltage_level": "电压等级",
    "drawing_number": "图号",
    "completeness": "完整度评估"
  }},
  "devices": [
    {{"type": "设备类型", "label": "编号", "spec": "规格", "count": 数量, "position": "位置"}}
  ],
  "topology": "系统拓扑描述（100字内）",
  "checks": [
    {{
      "rule_id": "规则编号",
      "category": "完整性/规范性/一致性/安全性",
      "title": "检查项标题",
      "detail": "简要检查结果（50字内）",
      "result": "✅通过 / ⚠️需改进 / ❌不通过 / ➖不适用",
      "suggestion": "改进建议（如有，60字内）",
      "gb_ref": "引用规范"
    }}
  ],
  "summary": {{
    "overall": "总体评价（150字内）",
    "issues": ["主要问题1", "主要问题2"],
    "suggestions": ["改进建议1", "改进建议2"]
  }}
}}
```

请严格按照上述格式输出，确保 JSON 完整闭合。"""
        
        elif mode == "draw":
            return """【当前模式：绘图模式 /Draw】

你是电气图纸绘制专家。请优先使用 AutoCAD COM 模式进行绘图操作：

## 绘图流程
1. **理解需求**：分析用户的绘图指令，确定需要绘制的电气设备和连接关系。
2. **COM 模式优先**：优先通过 AutoCAD COM 接口直接操作图纸（插入图元、绘制连线、添加标注）。
3. **回退策略**：如果 COM 模式不可用（AutoCAD 未连接或不支持），提供详细的绘图指导步骤。
4. **确认操作**：对关键操作在对话中明确说明将要执行的操作，获得用户确认后执行。

## 可用工具
- InsertElement：插入电气图元（变压器、断路器、隔离开关等）
- DrawConnection：绘制设备间连线
- AddAnnotation：添加文字标注
- ModifyElement：修改已有图元属性
- QueryDrawing：查询当前图纸信息"""
        
        else:  # auto
            return """【当前模式：自动模式 /Auto】

根据用户输入自动判断工作模式：
- 如果用户询问图纸审查、检查、审核相关问题 → 进入审查模式
- 如果用户要求绘图、添加设备、修改图纸 → 进入绘图模式
- 如果用户只是咨询问题 → 回答咨询

请根据具体情况灵活选择最合适的工作方式。"""

    @staticmethod
    def _fallback_response(user_input: str, error: str) -> str:
        """
        LLM 调用失败时的 Fallback 回复

        Args:
            user_input: 用户输入
            error: 错误信息

        Returns:
            基于规则的简单回复
        """
        lower_input = user_input.lower()
        if "变压器" in lower_input or "transformer" in lower_input:
            return "⚠️ AI 服务暂时不可用。要插入变压器，您可以直接告诉我：坐标位置和设备编号（如 T1），系统将自动插入 TR_2W 图块。"
        elif "断路器" in lower_input or "circuit breaker" in lower_input:
            return "⚠️ AI 服务暂时不可用。要插入断路器，请指定坐标和编号（如 QF1），系统将自动插入 CB_3P 图块。"
        elif "查询" in lower_input or "查看" in lower_input:
            return "⚠️ AI 服务暂时不可用。请点击工具栏中的「刷新图纸」按钮查看当前图元列表。"
        else:
            return f"⚠️ AI 服务暂时不可用（{error[:100]}），请稍后重试或检查 API Key 配置。"


# 会话级 Agent 注册表
_agent_registry: dict[str, DrawAgent] = {}


def get_agent(session_id: str) -> DrawAgent:
    """
    获取或创建会话 Agent（单例模式）

    Args:
        session_id: 会话 ID

    Returns:
        DrawAgent 实例
    """
    if session_id not in _agent_registry:
        _agent_registry[session_id] = DrawAgent(session_id)
        logger.info(f"DrawAgent created for session: {session_id}")
    return _agent_registry[session_id]
