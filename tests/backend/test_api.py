"""
Test Suite: FastAPI Route Layer
Tests for:
  - api/routes/chat.py       - POST /api/chat, GET /api/chat/stream,
                               POST /api/chat/confirm,
                               POST /api/chat/sessions, GET /api/chat/sessions
  - api/routes/symbols.py    - GET/POST/PUT/DELETE /api/symbols
  - api/middleware.py        - Exception handler middleware
  - main.py                  - GET /health
"""
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


# ============================================================
# Inject win32com stubs BEFORE importing any backend modules
# ============================================================

def _inject_win32_stubs() -> None:
    if "win32com" not in sys.modules:
        _stub = MagicMock()
        sys.modules["win32com"] = _stub
        sys.modules["win32com.client"] = _stub.client
    if "pywintypes" not in sys.modules:
        sys.modules["pywintypes"] = MagicMock()


_inject_win32_stubs()


# ============================================================
# Inject langchain stubs (langchain 1.x removed AgentExecutor)
# ============================================================

def _patch_langchain_agents() -> None:
    try:
        import langchain.agents as _lca
        if not hasattr(_lca, "AgentExecutor"):
            _lca.AgentExecutor = MagicMock(name="AgentExecutor")
            _lca.create_openai_tools_agent = MagicMock(name="create_openai_tools_agent")
    except ImportError:
        pass


_patch_langchain_agents()


# ============================================================
# Pre-import lazy-loaded modules so patch() can find them.
# chat.py imports these INSIDE function bodies; they must be
# in sys.modules before patch() is called.
# ============================================================

def _preload_lazy_modules() -> None:
    """Import modules referenced lazily inside chat.py route handlers."""
    try:
        import knowledge.rag_retriever   # noqa: F401
        import feedback.injector          # noqa: F401
        import agent.draw_agent           # noqa: F401
        import agent.context_manager      # noqa: F401
    except Exception:
        pass  # If any optional module fails, skip silently


_preload_lazy_modules()


# ============================================================
# Test DB engine & session factory (module-scoped)
# ============================================================

@pytest.fixture(scope="module")
def test_engine():
    """
    In-memory SQLite engine (StaticPool) with ALL ORM tables created.

    StaticPool ensures every session/connection reuses the SAME underlying
    sqlite3 connection, so tables created by create_all() are visible to all
    subsequent sessions.
    """
    from models.session import Base
    # Import all models so they register on Base.metadata
    import models.drawing_session   # noqa: F401
    import models.symbol            # noqa: F401
    import models.standard          # noqa: F401
    import models.feedback          # noqa: F401

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="module")
def test_session_factory(test_engine):
    return sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="module")
def client(test_session_factory):
    """
    TestClient with in-memory DB injected via dependency_overrides.
    The lifespan is executed but non-fatal startup failures are suppressed.
    """
    from main import app
    from models.session import get_db

    def override_get_db():
        session = test_session_factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# ============================================================
# Helpers
# ============================================================

def create_session_in_db(client: TestClient, title: str = "测试会话") -> str:
    """Create a session via the API and return its session_id."""
    resp = client.post("/api/chat/sessions", json={"title": title})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    return resp.json()["data"]["session_id"]


# ============================================================
# Test: Health endpoint
# ============================================================

class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_response_structure(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert "status" in data or "code" in data


# ============================================================
# Test: Session management
# ============================================================

class TestChatSessions:
    def test_create_session_returns_session_id(self, client):
        resp = client.post(
            "/api/chat/sessions",
            json={"title": "新会话"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert "session_id" in body["data"]

    def test_create_session_default_title(self, client):
        resp = client.post("/api/chat/sessions", json={})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["title"] == "新建会话"

    def test_list_sessions(self, client):
        client.post("/api/chat/sessions", json={"title": "会话A"})
        resp = client.get("/api/chat/sessions")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["data"], list)
        assert len(body["data"]) >= 1

    def test_get_messages_empty_for_new_session(self, client):
        session_id = create_session_in_db(client, "消息历史测试")
        resp = client.get(f"/api/chat/sessions/{session_id}/messages")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []

    def test_get_messages_404_for_unknown_session(self, client):
        resp = client.get("/api/chat/sessions/no-such-session/messages")
        assert resp.status_code == 404


# ============================================================
# Test: POST /api/chat (non-streaming)
#
# chat.py imports rag_retriever / rule_injector / get_agent lazily
# (inside the function body), so we must patch the original module
# symbols rather than api.routes.chat.<name>.
# ============================================================

class TestChatEndpoint:
    def test_chat_404_when_session_not_found(self, client):
        resp = client.post(
            "/api/chat",
            json={"session_id": "ghost-session", "message": "你好"},
        )
        assert resp.status_code == 404

    def test_chat_returns_agent_response(self, client):
        session_id = create_session_in_db(client, "对话测试")

        mock_agent = MagicMock()
        mock_agent.chat = AsyncMock(return_value="已为您插入变压器")

        with (
            patch("knowledge.rag_retriever.rag_retriever") as mock_rag,
            patch("feedback.injector.rule_injector") as mock_inj,
            patch("agent.draw_agent.get_agent", return_value=mock_agent),
        ):
            mock_rag.build_context = AsyncMock(return_value="规范上下文")
            mock_inj.inject.return_value = ("规范上下文", [])

            resp = client.post(
                "/api/chat",
                json={"session_id": session_id, "message": "插入变压器"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert "message" in body["data"]

    def test_chat_saves_user_and_assistant_messages(self, client):
        """After chatting, both user and assistant messages appear in history."""
        session_id = create_session_in_db(client, "保存消息测试")

        mock_agent = MagicMock()
        mock_agent.chat = AsyncMock(return_value="回复内容")

        with (
            patch("knowledge.rag_retriever.rag_retriever") as mock_rag,
            patch("feedback.injector.rule_injector") as mock_inj,
            patch("agent.draw_agent.get_agent", return_value=mock_agent),
        ):
            mock_rag.build_context = AsyncMock(return_value="")
            mock_inj.inject.return_value = ("", [])

            client.post(
                "/api/chat",
                json={"session_id": session_id, "message": "历史测试指令"},
            )

        resp = client.get(f"/api/chat/sessions/{session_id}/messages")
        messages = resp.json()["data"]
        roles = [m["role"] for m in messages]
        assert "user" in roles
        assert "assistant" in roles

    def test_chat_agent_error_returns_error_response(self, client):
        """When agent raises, the API returns an error-coded response (not uncaught 500)."""
        session_id = create_session_in_db(client, "Agent错误测试")

        mock_agent = MagicMock()
        mock_agent.chat = AsyncMock(side_effect=Exception("LLM timeout"))

        with (
            patch("knowledge.rag_retriever.rag_retriever") as mock_rag,
            patch("feedback.injector.rule_injector") as mock_inj,
            patch("agent.draw_agent.get_agent", return_value=mock_agent),
        ):
            mock_rag.build_context = AsyncMock(return_value="")
            mock_inj.inject.return_value = ("", [])

            resp = client.post(
                "/api/chat",
                json={"session_id": session_id, "message": "测试"},
            )

        # chat.py catches exceptions and returns ApiResponse(code=AGENT_TOOL_ERROR, ...)
        body = resp.json()
        if resp.status_code == 200:
            assert body["code"] != 0
        else:
            assert resp.status_code in (400, 500)


# ============================================================
# Test: GET /api/chat/stream (SSE)
# ============================================================

class TestChatStreamEndpoint:
    def test_stream_404_for_unknown_session(self, client):
        resp = client.get(
            "/api/chat/stream",
            params={"session_id": "no-session", "message": "hello"},
        )
        assert resp.status_code == 404

    def test_stream_returns_event_stream_content_type(self, client):
        session_id = create_session_in_db(client, "SSE类型测试")

        async def fake_stream(*args, **kwargs):
            yield "你好"
            yield "世界"

        mock_agent = MagicMock()
        mock_agent.chat_stream = fake_stream

        with (
            patch("knowledge.rag_retriever.rag_retriever") as mock_rag,
            patch("feedback.injector.rule_injector") as mock_inj,
            patch("agent.draw_agent.get_agent", return_value=mock_agent),
        ):
            mock_rag.build_context = AsyncMock(return_value="")
            mock_inj.inject.return_value = ("", [])

            resp = client.get(
                "/api/chat/stream",
                params={"session_id": session_id, "message": "流式测试"},
            )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_stream_response_contains_sse_data_prefix(self, client):
        session_id = create_session_in_db(client, "SSE数据测试")

        async def fake_stream(*args, **kwargs):
            yield "token1"

        mock_agent = MagicMock()
        mock_agent.chat_stream = fake_stream

        with (
            patch("knowledge.rag_retriever.rag_retriever") as mock_rag,
            patch("feedback.injector.rule_injector") as mock_inj,
            patch("agent.draw_agent.get_agent", return_value=mock_agent),
        ):
            mock_rag.build_context = AsyncMock(return_value="")
            mock_inj.inject.return_value = ("", [])

            resp = client.get(
                "/api/chat/stream",
                params={"session_id": session_id, "message": "token测试"},
            )

        assert resp.status_code == 200
        assert b"data:" in resp.content


# ============================================================
# Test: POST /api/chat/confirm
# ============================================================

class TestChatConfirm:
    def test_confirm_returns_error_when_no_pending_plan(self, client):
        session_id = create_session_in_db(client, "无计划确认测试")

        mock_context = MagicMock()
        mock_context.get_pending_plan.return_value = None

        with patch("agent.context_manager.get_context", return_value=mock_context):
            resp = client.post(
                "/api/chat/confirm",
                json={"session_id": session_id, "confirm": True},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] != 0  # "no pending plan" returns non-zero code

    def test_confirm_true_clears_pending_plan(self, client):
        session_id = create_session_in_db(client, "确认执行测试")

        mock_context = MagicMock()
        mock_context.get_pending_plan.return_value = {"action": "insert", "element": "CB_3P"}

        with patch("agent.context_manager.get_context", return_value=mock_context):
            resp = client.post(
                "/api/chat/confirm",
                json={"session_id": session_id, "confirm": True},
            )

        assert resp.status_code == 200
        mock_context.clear_pending_plan.assert_called_once()
        body = resp.json()
        assert body["code"] == 0

    def test_confirm_false_also_clears_pending_plan(self, client):
        session_id = create_session_in_db(client, "取消计划测试")

        mock_context = MagicMock()
        mock_context.get_pending_plan.return_value = {"action": "delete"}

        with patch("agent.context_manager.get_context", return_value=mock_context):
            resp = client.post(
                "/api/chat/confirm",
                json={"session_id": session_id, "confirm": False},
            )

        assert resp.status_code == 200
        mock_context.clear_pending_plan.assert_called_once()


# ============================================================
# Test: Middleware – exception handlers
# ============================================================

class TestMiddleware:
    def test_404_on_unknown_route(self, client):
        resp = client.get("/api/this-route-does-not-exist-xyz")
        assert resp.status_code == 404

    def test_method_not_allowed_on_sessions(self, client):
        # DELETE /api/chat/sessions is not a registered route
        resp = client.delete("/api/chat/sessions")
        assert resp.status_code in (404, 405)


# ============================================================
# Test: Symbols API (integration with in-memory DB)
# ============================================================

class TestSymbolsAPI:
    def test_list_symbols_returns_200(self, client):
        resp = client.get("/api/symbols")
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body

    def test_create_symbol_success(self, client):
        resp = client.post(
            "/api/symbols",
            json={
                "symbol_id": "API_TEST_SYM",
                "name": "API测试符号",
                "name_en": "API Test Symbol",
                "category": "protection",
                "block_name": "TEST_BLOCK",
                "layer": "ELEC-SYMBOL",
                "width": 4.0,
                "height": 4.0,
                "tags": ["test"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0

    def test_create_duplicate_symbol_returns_error(self, client):
        payload = {"symbol_id": "DUP_SYM_777", "name": "重复符号"}
        client.post("/api/symbols", json=payload)
        resp = client.post("/api/symbols", json=payload)
        if resp.status_code == 200:
            assert resp.json()["code"] != 0
        else:
            assert resp.status_code == 400

    def test_get_symbol_by_id(self, client):
        client.post(
            "/api/symbols",
            json={"symbol_id": "GET_SYM_777", "name": "获取测试"},
        )
        resp = client.get("/api/symbols/GET_SYM_777")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["symbol_id"] == "GET_SYM_777"

    def test_get_nonexistent_symbol_returns_404(self, client):
        resp = client.get("/api/symbols/GHOST_SYM_99999")
        assert resp.status_code == 404

    def test_delete_symbol_success(self, client):
        client.post(
            "/api/symbols",
            json={"symbol_id": "DEL_SYM_777", "name": "删除测试"},
        )
        resp = client.delete("/api/symbols/DEL_SYM_777")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0

        # Confirm it's gone
        get_resp = client.get("/api/symbols/DEL_SYM_777")
        assert get_resp.status_code == 404
