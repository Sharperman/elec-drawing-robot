"""
Test Suite: DrawAgent
Tests for:
  - agent/draw_agent.py  - DrawAgent.chat(), chat_stream(), get_agent(), _fallback_response()
  - agent/prompts/system_prompt.py - build_system_prompt()
"""
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================
# Inject langchain stubs for APIs removed in langchain >= 1.0
# (AgentExecutor / create_openai_tools_agent are now in langgraph-prebuilt)
# This is required because draw_agent.py imports from langchain.agents which
# no longer exports these names in langchain 1.x — see SOURCE BUG below.
# ============================================================

def _patch_langchain_agents():
    try:
        import langchain.agents as _lca
        if not hasattr(_lca, "AgentExecutor"):
            _lca.AgentExecutor = MagicMock(name="AgentExecutor")
            _lca.create_openai_tools_agent = MagicMock(name="create_openai_tools_agent")
    except ImportError:
        pass

_patch_langchain_agents()


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def mock_settings():
    """Provide minimal settings so tests don't need a real .env."""
    with patch("agent.draw_agent.settings", create=True) as s:
        s.MODEL_NAME = "gpt-4o"
        s.OPENAI_API_KEY = "sk-test"
        s.OPENAI_BASE_URL = "https://api.openai.com/v1"
        s.LLM_TEMPERATURE = 0.0
        s.LLM_MAX_TOKENS = 2048
        s.AGENT_VERBOSE = False
        s.AGENT_MAX_ITERATIONS = 5
        yield s


# ============================================================
# Test: DrawAgent._fallback_response
# ============================================================


class TestDrawAgentFallbackResponse:
    """Tests for the static _fallback_response method (no LLM required)."""

    def test_transformer_keyword_triggers_specific_hint(self):
        from agent.draw_agent import DrawAgent

        resp = DrawAgent._fallback_response("插入变压器 T1", "api_error")
        assert "TR_2W" in resp
        assert "变压器" in resp

    def test_circuit_breaker_keyword_triggers_specific_hint(self):
        from agent.draw_agent import DrawAgent

        resp = DrawAgent._fallback_response("添加断路器 QF1", "timeout")
        assert "CB_3P" in resp

    def test_query_keyword_triggers_query_hint(self):
        from agent.draw_agent import DrawAgent

        resp = DrawAgent._fallback_response("查询当前图纸元素", "llm_down")
        assert "查询" in resp or "刷新" in resp

    def test_generic_fallback_includes_error_snippet(self):
        from agent.draw_agent import DrawAgent

        resp = DrawAgent._fallback_response("画个圆", "connection timeout error")
        assert "connection timeout" in resp or "暂时不可用" in resp

    def test_english_transformer_keyword(self):
        from agent.draw_agent import DrawAgent

        resp = DrawAgent._fallback_response("insert transformer", "err")
        assert "TR_2W" in resp

    def test_english_circuit_breaker_keyword(self):
        from agent.draw_agent import DrawAgent

        resp = DrawAgent._fallback_response("place circuit breaker", "err")
        assert "CB_3P" in resp


# ============================================================
# Test: get_agent registry
# ============================================================


class TestGetAgent:
    """Tests for get_agent() session registry."""

    def test_returns_draw_agent_instance(self):
        from agent.draw_agent import get_agent, DrawAgent, _agent_registry

        _agent_registry.clear()
        agent = get_agent("session-001")
        assert isinstance(agent, DrawAgent)

    def test_same_session_id_returns_same_instance(self):
        from agent.draw_agent import get_agent, _agent_registry

        _agent_registry.clear()
        a1 = get_agent("session-abc")
        a2 = get_agent("session-abc")
        assert a1 is a2

    def test_different_sessions_return_different_instances(self):
        from agent.draw_agent import get_agent, _agent_registry

        _agent_registry.clear()
        a1 = get_agent("session-X")
        a2 = get_agent("session-Y")
        assert a1 is not a2

    def test_agent_has_correct_session_id(self):
        from agent.draw_agent import get_agent, _agent_registry

        _agent_registry.clear()
        agent = get_agent("my-special-session")
        assert agent.session_id == "my-special-session"


# ============================================================
# Test: DrawAgent.chat (non-streaming)
# ============================================================


class TestDrawAgentChat:
    """Tests for DrawAgent.chat() using mocked AgentExecutor."""

    @pytest.mark.asyncio
    async def test_chat_returns_output_string(self):
        from agent.draw_agent import DrawAgent

        agent = DrawAgent("test-session-chat")

        mock_executor = AsyncMock()
        mock_executor.ainvoke = AsyncMock(return_value={"output": "已插入变压器"})

        with patch.object(agent, "_build_executor", return_value=mock_executor):
            result = await agent.chat(user_input="插入变压器")

        assert result == "已插入变压器"

    @pytest.mark.asyncio
    async def test_chat_updates_message_history(self):
        from agent.draw_agent import DrawAgent

        agent = DrawAgent("test-session-history")

        mock_executor = AsyncMock()
        mock_executor.ainvoke = AsyncMock(return_value={"output": "执行完毕"})

        with patch.object(agent, "_build_executor", return_value=mock_executor):
            await agent.chat(user_input="删除元件 E1")

        assert len(agent._message_history) == 2
        assert agent._message_history[0].content == "删除元件 E1"
        assert agent._message_history[1].content == "执行完毕"

    @pytest.mark.asyncio
    async def test_chat_falls_back_on_exception(self):
        from agent.draw_agent import DrawAgent

        agent = DrawAgent("test-session-fallback")

        mock_executor = AsyncMock()
        mock_executor.ainvoke = AsyncMock(side_effect=Exception("LLM down"))

        with patch.object(agent, "_build_executor", return_value=mock_executor):
            result = await agent.chat(user_input="测试指令")

        # Should return a fallback string, not raise
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_chat_passes_standards_context_to_build_executor(self):
        from agent.draw_agent import DrawAgent

        agent = DrawAgent("test-ctx-pass")
        captured = {}

        def fake_build(standards_context="", learned_rules=None):
            captured["ctx"] = standards_context
            exec_mock = AsyncMock()
            exec_mock.ainvoke = AsyncMock(return_value={"output": "ok"})
            return exec_mock

        with patch.object(agent, "_build_executor", side_effect=fake_build):
            await agent.chat(
                user_input="test",
                standards_context="GB/T 4728-2018",
            )

        assert captured["ctx"] == "GB/T 4728-2018"

    @pytest.mark.asyncio
    async def test_chat_history_capped_at_20(self):
        """Only the last 20 messages are passed to the executor."""
        from agent.draw_agent import DrawAgent
        from langchain_core.messages import HumanMessage, AIMessage

        agent = DrawAgent("test-session-cap")
        # Pre-fill history with 22 messages (11 pairs)
        for i in range(11):
            agent._message_history.append(HumanMessage(content=f"q{i}"))
            agent._message_history.append(AIMessage(content=f"a{i}"))

        captured_inputs = []

        def fake_build(standards_context="", learned_rules=None):
            exec_mock = AsyncMock()

            async def fake_invoke(inp):
                captured_inputs.append(inp)
                return {"output": "res"}

            exec_mock.ainvoke = fake_invoke
            return exec_mock

        with patch.object(agent, "_build_executor", side_effect=fake_build):
            await agent.chat(user_input="latest question")

        assert len(captured_inputs[0]["chat_history"]) <= 20


# ============================================================
# Test: DrawAgent.clear_history
# ============================================================


class TestDrawAgentClearHistory:
    def test_clear_history_empties_message_list(self):
        from agent.draw_agent import DrawAgent
        from langchain_core.messages import HumanMessage

        agent = DrawAgent("test-clear")
        agent._message_history.append(HumanMessage(content="hello"))
        agent.clear_history()
        assert agent._message_history == []


# ============================================================
# Test: build_system_prompt
# ============================================================


class TestBuildSystemPrompt:
    """Unit tests for the system prompt builder."""

    def test_returns_non_empty_string(self):
        from agent.prompts.system_prompt import build_system_prompt

        prompt = build_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 50

    def test_includes_standards_context(self):
        from agent.prompts.system_prompt import build_system_prompt

        prompt = build_system_prompt(standards_context="GB/T 4728-2018 规范内容")
        assert "GB/T 4728-2018" in prompt

    def test_includes_learned_rules(self):
        from agent.prompts.system_prompt import build_system_prompt

        rules = ["不得使用图层 0 插入图元", "断路器标识必须大写"]
        prompt = build_system_prompt(learned_rules=rules)
        assert "不得使用图层 0" in prompt

    def test_no_rules_still_returns_valid_prompt(self):
        from agent.prompts.system_prompt import build_system_prompt

        prompt = build_system_prompt(standards_context="", learned_rules=None)
        assert isinstance(prompt, str)
        assert len(prompt) > 0
