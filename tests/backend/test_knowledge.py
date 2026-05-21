"""
Test Suite: Knowledge Layer
Tests for:
  - knowledge/symbol_library.py  - SymbolLibrary CRUD
  - api/schemas.py               - Pydantic validation (FeedbackRequest, ChatRequest, etc.)
  - feedback/collector.py        - FeedbackCollector.collect()
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# ============================================================
# SQLite in-memory DB fixture
# ============================================================


@pytest.fixture(scope="function")
def db_session():
    """
    Provide a clean SQLite in-memory session for each test.
    Creates all tables and tears down afterwards.
    """
    from models.session import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def symbol_library(db_session):
    from knowledge.symbol_library import SymbolLibrary
    return SymbolLibrary(db_session)


@pytest.fixture
def sample_symbol(symbol_library):
    """Create and return a sample Symbol in the DB."""
    return symbol_library.create(
        symbol_id="TEST_CB",
        name="测试断路器",
        name_en="Test Circuit Breaker",
        category="protection",
        block_name="CB_3P",
        layer="ELEC-SYMBOL",
        width=4.0,
        height=4.0,
        tags=["断路器", "保护"],
    )


# ============================================================
# Test: SymbolLibrary.create
# ============================================================


class TestSymbolLibraryCreate:
    def test_create_returns_symbol_with_correct_id(self, symbol_library):
        sym = symbol_library.create(
            symbol_id="NEW_SYM",
            name="新图元",
        )
        assert sym.symbol_id == "NEW_SYM"
        assert sym.name == "新图元"

    def test_create_sets_defaults(self, symbol_library):
        sym = symbol_library.create(symbol_id="DEF_SYM", name="默认")
        assert sym.category == "general"
        assert sym.layer == "ELEC-SYMBOL"
        assert sym.width == 1.0
        assert sym.height == 1.0

    def test_create_tags_stored_as_json(self, symbol_library):
        sym = symbol_library.create(
            symbol_id="TAG_SYM",
            name="标签图元",
            tags=["高压", "母线"],
        )
        tags = json.loads(sym.tags)
        assert "高压" in tags
        assert "母线" in tags

    def test_create_duplicate_raises_value_error(self, symbol_library, sample_symbol):
        with pytest.raises(ValueError, match="already exists"):
            symbol_library.create(
                symbol_id="TEST_CB",
                name="重复ID",
            )

    def test_create_persists_to_db(self, db_session, symbol_library):
        symbol_library.create(symbol_id="PERSIST_SYM", name="持久化测试")
        found = symbol_library.get_by_id("PERSIST_SYM")
        assert found is not None
        assert found.name == "持久化测试"


# ============================================================
# Test: SymbolLibrary.get_by_id
# ============================================================


class TestSymbolLibraryGetById:
    def test_get_existing_symbol(self, symbol_library, sample_symbol):
        sym = symbol_library.get_by_id("TEST_CB")
        assert sym is not None
        assert sym.symbol_id == "TEST_CB"

    def test_get_nonexistent_symbol_returns_none(self, symbol_library):
        sym = symbol_library.get_by_id("DOES_NOT_EXIST")
        assert sym is None

    def test_get_inactive_symbol_returns_none(self, symbol_library, sample_symbol):
        # Soft-delete then try to get
        symbol_library.delete("TEST_CB")
        sym = symbol_library.get_by_id("TEST_CB")
        assert sym is None


# ============================================================
# Test: SymbolLibrary.list_all
# ============================================================


class TestSymbolLibraryListAll:
    def test_list_all_returns_created_symbols(self, symbol_library, sample_symbol):
        items, total = symbol_library.list_all()
        assert total >= 1
        ids = [s.symbol_id for s in items]
        assert "TEST_CB" in ids

    def test_list_all_filter_by_category(self, symbol_library):
        symbol_library.create("PROT1", "保护1", category="protection")
        symbol_library.create("LINE1", "导线1", category="line")

        items, total = symbol_library.list_all(category="protection")
        for s in items:
            assert s.category == "protection"

    def test_list_all_search_by_name(self, symbol_library):
        symbol_library.create("SEARCHABLE", "可搜索变压器")
        items, total = symbol_library.list_all(search="变压器")
        names = [s.name for s in items]
        assert any("变压器" in n for n in names)

    def test_list_all_pagination(self, symbol_library):
        for i in range(5):
            symbol_library.create(f"PAGE_SYM_{i}", f"分页符号{i}")

        page1, total1 = symbol_library.list_all(page=1, page_size=2)
        page2, total2 = symbol_library.list_all(page=2, page_size=2)

        assert len(page1) == 2
        # IDs should not overlap between pages
        p1_ids = {s.symbol_id for s in page1}
        p2_ids = {s.symbol_id for s in page2}
        assert p1_ids.isdisjoint(p2_ids)

    def test_list_all_excludes_deleted_symbols(self, symbol_library, sample_symbol):
        symbol_library.delete("TEST_CB")
        items, total = symbol_library.list_all()
        ids = [s.symbol_id for s in items]
        assert "TEST_CB" not in ids


# ============================================================
# Test: SymbolLibrary.update
# ============================================================


class TestSymbolLibraryUpdate:
    def test_update_name(self, symbol_library, sample_symbol):
        updated = symbol_library.update("TEST_CB", name="已更新名称")
        assert updated.name == "已更新名称"

    def test_update_nonexistent_returns_none(self, symbol_library):
        result = symbol_library.update("NO_SUCH_ID", name="x")
        assert result is None

    def test_update_tags_as_list(self, symbol_library, sample_symbol):
        updated = symbol_library.update("TEST_CB", tags=["新标签"])
        tags = json.loads(updated.tags)
        assert "新标签" in tags

    def test_update_ignores_unlisted_fields(self, symbol_library, sample_symbol):
        # 'category' is NOT in allowed_fields of update() – it should be silently ignored
        original_category = sample_symbol.category
        symbol_library.update("TEST_CB", category="HACKED_CATEGORY")
        sym = symbol_library.get_by_id("TEST_CB")
        assert sym.category == original_category  # unchanged (category is not whitelisted)


# ============================================================
# Test: SymbolLibrary.delete
# ============================================================


class TestSymbolLibraryDelete:
    def test_delete_returns_true_for_existing_symbol(self, symbol_library, sample_symbol):
        result = symbol_library.delete("TEST_CB")
        assert result is True

    def test_delete_sets_is_active_false(self, db_session, symbol_library, sample_symbol):
        from models.symbol import Symbol
        symbol_library.delete("TEST_CB")
        sym = db_session.query(Symbol).filter_by(symbol_id="TEST_CB").first()
        assert sym.is_active is False

    def test_delete_nonexistent_returns_false(self, symbol_library):
        result = symbol_library.delete("GHOST_SYM")
        assert result is False


# ============================================================
# Test: SymbolLibrary.search_by_name
# ============================================================


class TestSymbolLibrarySearchByName:
    def test_search_finds_matching_symbols(self, symbol_library):
        symbol_library.create("SRCH1", "高压断路器")
        symbol_library.create("SRCH2", "低压断路器")
        symbol_library.create("SRCH3", "变压器")

        results = symbol_library.search_by_name("断路器")
        names = [s.name for s in results]
        assert "高压断路器" in names
        assert "低压断路器" in names
        assert "变压器" not in names

    def test_search_respects_limit(self, symbol_library):
        for i in range(10):
            symbol_library.create(f"LSYM_{i}", f"导线符号{i}")

        results = symbol_library.search_by_name("导线符号", limit=3)
        assert len(results) <= 3

    def test_search_empty_if_no_match(self, symbol_library):
        results = symbol_library.search_by_name("完全不存在的名字XYZ")
        assert results == []


# ============================================================
# Test: Pydantic Schema Validation
# ============================================================


class TestFeedbackRequestValidation:
    """Tests for the FeedbackRequest validator."""

    def test_valid_feedback_type_positive(self):
        from api.schemas import FeedbackRequest
        fb = FeedbackRequest(
            session_id="sess-1",
            feedback_type="positive",
        )
        assert fb.feedback_type == "positive"

    @pytest.mark.parametrize("ft", ["positive", "negative", "correction", "suggestion"])
    def test_all_valid_feedback_types(self, ft):
        from api.schemas import FeedbackRequest
        fb = FeedbackRequest(session_id="s", feedback_type=ft)
        assert fb.feedback_type == ft

    def test_invalid_feedback_type_raises(self):
        from api.schemas import FeedbackRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            FeedbackRequest(session_id="s", feedback_type="invalid_type")

    def test_rating_must_be_1_to_5(self):
        from api.schemas import FeedbackRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            FeedbackRequest(session_id="s", feedback_type="positive", rating=0)
        with pytest.raises(ValidationError):
            FeedbackRequest(session_id="s", feedback_type="positive", rating=6)

    def test_rating_valid_boundary_values(self):
        from api.schemas import FeedbackRequest
        fb1 = FeedbackRequest(session_id="s", feedback_type="positive", rating=1)
        fb5 = FeedbackRequest(session_id="s", feedback_type="positive", rating=5)
        assert fb1.rating == 1
        assert fb5.rating == 5


class TestChatRequestValidation:
    def test_valid_chat_request(self):
        from api.schemas import ChatRequest
        req = ChatRequest(session_id="s1", message="插入变压器")
        assert req.message == "插入变压器"

    def test_empty_message_raises(self):
        from api.schemas import ChatRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ChatRequest(session_id="s1", message="")

    def test_message_too_long_raises(self):
        from api.schemas import ChatRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ChatRequest(session_id="s1", message="x" * 4097)


class TestApiResponseDefaults:
    def test_default_code_is_zero(self):
        from api.schemas import ApiResponse
        r = ApiResponse()
        assert r.code == 0

    def test_default_message_is_success(self):
        from api.schemas import ApiResponse
        r = ApiResponse()
        assert r.message == "success"

    def test_data_can_be_arbitrary(self):
        from api.schemas import ApiResponse
        r = ApiResponse(data={"key": "value", "num": 42})
        assert r.data["key"] == "value"


# ============================================================
# Test: FeedbackCollector
# ============================================================


class TestFeedbackCollector:
    def test_collect_saves_feedback_to_db(self, db_session):
        from feedback.collector import FeedbackCollector
        from models.feedback import UserFeedback

        # Patch settings via config module (imported locally inside _check_refine_trigger)
        with patch("config.settings") as mock_s:
            mock_s.FEEDBACK_REFINE_THRESHOLD = 9999

            collector = FeedbackCollector(db_session)
            fb = collector.collect(
                session_id="sess-feedback",
                feedback_type="positive",
                original_input="插入断路器",
                agent_output="已插入断路器 QF1",
                user_comment="很好",
                rating=5,
            )

        assert fb.id is not None
        assert fb.feedback_type == "positive"
        assert fb.rating == 5

        # Verify persistence
        saved = db_session.query(UserFeedback).filter_by(id=fb.id).first()
        assert saved is not None
        assert saved.user_comment == "很好"

    def test_collect_sets_is_processed_false(self, db_session):
        from feedback.collector import FeedbackCollector

        with patch("config.settings") as mock_s:
            mock_s.FEEDBACK_REFINE_THRESHOLD = 9999

            collector = FeedbackCollector(db_session)
            fb = collector.collect(
                session_id="sess-proc",
                feedback_type="negative",
            )

        assert fb.is_processed is False

    def test_collect_with_correction(self, db_session):
        from feedback.collector import FeedbackCollector

        with patch("config.settings") as mock_s:
            mock_s.FEEDBACK_REFINE_THRESHOLD = 9999

            collector = FeedbackCollector(db_session)
            fb = collector.collect(
                session_id="sess-corr",
                feedback_type="correction",
                correction="应使用 ELEC-PROTECTION 图层",
            )

        assert fb.correction == "应使用 ELEC-PROTECTION 图层"

    def test_get_feedbacks_returns_list(self, db_session):
        from feedback.collector import FeedbackCollector

        with patch("config.settings") as mock_s:
            mock_s.FEEDBACK_REFINE_THRESHOLD = 9999

            collector = FeedbackCollector(db_session)
            collector.collect("sess-list", "positive")
            collector.collect("sess-list", "negative")

            feedbacks = collector.get_feedbacks(session_id="sess-list")

        assert len(feedbacks) >= 2

    def test_get_feedbacks_filter_by_type(self, db_session):
        from feedback.collector import FeedbackCollector

        with patch("config.settings") as mock_s:
            mock_s.FEEDBACK_REFINE_THRESHOLD = 9999

            collector = FeedbackCollector(db_session)
            collector.collect("sess-type", "positive")
            collector.collect("sess-type", "negative")

            pos = collector.get_feedbacks(
                session_id="sess-type",
                feedback_type="positive",
            )

        assert all(f.feedback_type == "positive" for f in pos)
