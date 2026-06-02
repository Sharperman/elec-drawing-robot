"""
LangChain Agent 初始化
AgentExecutor + 5 个 Tool + Memory + 规范上下文注入
"""
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

    def _build_executor(self, standards_context: str = "", learned_rules: Optional[list[str]] = None) -> AgentExecutor:
        """
        构建 AgentExecutor（每次调用时动态构建以注入最新规范）

        Args:
            standards_context: 从 RAG 检索的规范上下文
            learned_rules: 学习规则列表

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

        # 系统提示词（含规范上下文）
        system_prompt = build_system_prompt(
            standards_context=standards_context,
            learned_rules=learned_rules,
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
    ) -> str:
        """
        单轮对话（非流式）

        Args:
            user_input: 用户输入
            image_data: 附带图片 base64
            standards_context: 规范上下文
            learned_rules: 学习规则

        Returns:
            Agent 回复字符串
        """
        executor = self._build_executor(standards_context, learned_rules)

        # 构建输入
        agent_input: dict = {
            "input": user_input,
            "chat_history": self._message_history[-20:],  # 保留最近 20 条
        }

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
    ) -> AsyncIterator[str]:
        """
        流式对话（生成 SSE token）

        Yields:
            token 字符串片段
        """
        from config import settings
        from agent.tools import (
            InsertElementTool, DrawConnectionTool,
            AddAnnotationTool, ModifyElementTool, QueryDrawingTool,
        )
        from agent.prompts.system_prompt import build_system_prompt
        from langchain_core.callbacks import AsyncCallbackHandler

        system_prompt = build_system_prompt(standards_context, learned_rules)

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
                        yield token
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "tool")
                    tool_input = str(event["data"].get("input", ""))[:100]
                    yield f"\n\n🔧 **调用工具**: `{tool_name}`\n```\n{tool_input}\n```\n"
                elif kind == "on_tool_end":
                    tool_output = str(event["data"].get("output", ""))[:200]
                    yield f"✅ 工具结果: {tool_output}\n\n"

            # 更新历史
            self._message_history.append(HumanMessage(content=user_input))
            self._message_history.append(AIMessage(content=full_output))

        except Exception as e:
            logger.error(f"DrawAgent.chat_stream failed: {e}")
            error_msg = self._fallback_response(user_input, str(e))
            yield error_msg

    def clear_history(self) -> None:
        """清除对话历史"""
        self._message_history.clear()

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
