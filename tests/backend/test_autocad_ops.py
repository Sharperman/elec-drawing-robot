"""
Test Suite: AutoCAD Operations
Tests for:
  - autocad/retry.py         - retry_on_com_error decorator
  - autocad/transaction.py   - AutoCADTransaction context manager
  - autocad/drawing_ops.py   - DrawingOps methods (mocked COM layer)
"""
import sys
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

# ============================================================
# Module-level mock for win32com so drawing_ops can be imported
# on non-Windows CI environments
# ============================================================

def _inject_win32_stubs():
    """Inject minimal win32com stubs into sys.modules if the real package is absent."""
    if "win32com" not in sys.modules:
        win32com_stub = MagicMock()
        win32com_stub.client = MagicMock()
        win32com_stub.client.pythoncom = MagicMock()
        win32com_stub.client.pythoncom.VT_ARRAY = 8192
        win32com_stub.client.pythoncom.VT_R8 = 5
        sys.modules.setdefault("win32com", win32com_stub)
        sys.modules.setdefault("win32com.client", win32com_stub.client)
        sys.modules.setdefault("pywintypes", MagicMock())

_inject_win32_stubs()


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def mock_autocad_connection():
    """Mock the autocad_connection singleton so no real COM calls are made."""
    with patch("autocad.drawing_ops.autocad_connection") as mock_conn:
        mock_doc = MagicMock()
        mock_model_space = MagicMock()
        mock_conn.doc = mock_doc
        mock_conn.model_space = mock_model_space
        yield mock_conn, mock_doc, mock_model_space


@pytest.fixture
def mock_txn_connection():
    """Mock autocad_connection for transaction tests."""
    with patch("autocad.transaction.autocad_connection") as mock_conn:
        mock_doc = MagicMock()
        mock_conn.doc = mock_doc
        yield mock_conn, mock_doc


# ============================================================
# Test: retry_on_com_error decorator
# ============================================================


class TestRetryOnComError:
    """Unit tests for the retry_on_com_error decorator."""

    def test_success_on_first_attempt(self):
        """Function succeeds immediately; no retries occur."""
        from autocad.retry import retry_on_com_error

        call_count = 0

        @retry_on_com_error
        def always_ok():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = always_ok()
        assert result == "ok"
        assert call_count == 1

    def test_raises_connection_error_immediately(self):
        """ConnectionError bypasses retry logic and is re-raised immediately."""
        from autocad.retry import retry_on_com_error

        call_count = 0

        @retry_on_com_error
        def connection_error_func():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("AutoCAD not running")

        with pytest.raises(ConnectionError, match="AutoCAD not running"):
            connection_error_func()

        assert call_count == 1  # Must NOT retry

    def test_non_com_exception_raises_immediately(self):
        """Non-COM exceptions (e.g. ValueError) are re-raised without retrying."""
        from autocad.retry import retry_on_com_error

        call_count = 0

        @retry_on_com_error
        def value_error_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("bad input")

        with pytest.raises(ValueError, match="bad input"):
            value_error_func()

        assert call_count == 1

    def test_retries_on_com_error_and_ultimately_raises(self):
        """COM-like errors trigger retries up to max_retries then raises RuntimeError."""
        from autocad.retry import retry_on_com_error

        # Simulate a COM error by using an exception class with "com_error" in its name
        class com_error(Exception):
            pass

        call_count = 0

        @retry_on_com_error(max_retries=3, initial_delay=0.0, backoff_factor=1.0)
        def always_com_error():
            nonlocal call_count
            call_count += 1
            raise com_error("COM failed")

        with pytest.raises(RuntimeError, match="重试"):
            always_com_error()

        assert call_count == 3

    def test_retries_on_com_error_succeeds_on_second_attempt(self):
        """COM error on first call, success on second call returns the result."""
        from autocad.retry import retry_on_com_error

        class com_error(Exception):
            pass

        attempts = []

        @retry_on_com_error(max_retries=3, initial_delay=0.0, backoff_factor=1.0)
        def eventually_ok():
            attempts.append(1)
            if len(attempts) == 1:
                raise com_error("transient")
            return "success"

        result = eventually_ok()
        assert result == "success"
        assert len(attempts) == 2

    def test_parametrized_decorator_syntax(self):
        """Decorator used as @retry_on_com_error(max_retries=2) works correctly."""
        from autocad.retry import retry_on_com_error

        call_count = 0

        @retry_on_com_error(max_retries=2, initial_delay=0.0)
        def ok_func():
            nonlocal call_count
            call_count += 1
            return 42

        assert ok_func() == 42
        assert call_count == 1

    def test_reraise_false_returns_none_after_exhaustion(self):
        """With reraise=False, exhausted retries return None instead of raising."""
        from autocad.retry import retry_on_com_error

        class com_error(Exception):
            pass

        @retry_on_com_error(max_retries=2, initial_delay=0.0, reraise=False)
        def always_fails():
            raise com_error("oops")

        result = always_fails()
        assert result is None


# ============================================================
# Test: AutoCADTransaction
# ============================================================


class TestAutoCADTransaction:
    """Unit tests for AutoCADTransaction context manager."""

    def test_enter_calls_start_undo_mark(self, mock_txn_connection):
        """__enter__ calls doc.StartUndoMark()."""
        from autocad.transaction import AutoCADTransaction

        _, mock_doc = mock_txn_connection

        txn = AutoCADTransaction("test-txn")
        with txn:
            txn.commit()

        mock_doc.StartUndoMark.assert_called_once()

    def test_commit_calls_end_undo_mark(self, mock_txn_connection):
        """commit() calls doc.EndUndoMark() and sets _committed=True."""
        from autocad.transaction import AutoCADTransaction

        _, mock_doc = mock_txn_connection

        txn = AutoCADTransaction("test-commit")
        with txn:
            txn.commit()

        mock_doc.EndUndoMark.assert_called_once()
        assert txn._committed is True

    def test_rollback_on_exception(self, mock_txn_connection):
        """Exception inside context triggers rollback (SendCommand UNDO)."""
        from autocad.transaction import AutoCADTransaction

        _, mock_doc = mock_txn_connection

        txn = AutoCADTransaction("test-rollback")
        with pytest.raises(RuntimeError):
            with txn:
                raise RuntimeError("drawing failed")

        mock_doc.SendCommand.assert_called_once()
        cmd_arg = mock_doc.SendCommand.call_args[0][0]
        assert "UNDO" in cmd_arg

    def test_rollback_when_no_commit(self, mock_txn_connection):
        """Exiting without commit also triggers rollback."""
        from autocad.transaction import AutoCADTransaction

        _, mock_doc = mock_txn_connection

        with AutoCADTransaction("no-commit"):
            pass  # no commit()

        mock_doc.SendCommand.assert_called_once()

    def test_context_manager_function_form(self, mock_txn_connection):
        """autocad_transaction() function form works correctly."""
        from autocad.transaction import autocad_transaction

        _, mock_doc = mock_txn_connection

        with autocad_transaction("func-form") as txn:
            txn.commit()

        mock_doc.StartUndoMark.assert_called_once()
        mock_doc.EndUndoMark.assert_called_once()

    def test_enter_gracefully_handles_connection_error(self):
        """If StartUndoMark raises, __enter__ logs warning and does NOT propagate."""
        from autocad.transaction import AutoCADTransaction

        with patch("autocad.transaction.autocad_connection") as mock_conn:
            mock_doc = MagicMock()
            mock_doc.StartUndoMark.side_effect = Exception("not connected")
            mock_conn.doc = mock_doc

            txn = AutoCADTransaction("graceful-error")
            # Should not raise
            with txn:
                pass  # _entered is False so rollback skips SendCommand


# ============================================================
# Helpers for DrawingOps tests
# ============================================================


def _make_win32_mock():
    """Return a win32com.client mock with VT_ARRAY / VT_R8 constants."""
    mock_win32 = MagicMock()
    mock_win32.VARIANT.side_effect = lambda t, v: v  # just return the value list
    mock_win32.pythoncom.VT_ARRAY = 8192
    mock_win32.pythoncom.VT_R8 = 5
    return mock_win32


# ============================================================
# Test: DrawingOps
# ============================================================


class TestDrawingOps:
    """Unit tests for DrawingOps (COM layer fully mocked)."""

    def test_insert_block_returns_handle(self, mock_autocad_connection):
        """insert_block returns the block_ref.Handle string."""
        from autocad.drawing_ops import DrawingOps

        _, mock_doc, mock_model_space = mock_autocad_connection

        mock_block_ref = MagicMock()
        mock_block_ref.Handle = "A1B2C3"
        mock_block_ref.HasAttributes = False
        mock_model_space.InsertBlock.return_value = mock_block_ref

        ops = DrawingOps()
        # Patch win32com inside sys.modules so the local import inside _run resolves
        mock_win32 = _make_win32_mock()
        with patch.dict(sys.modules, {"win32com": mock_win32, "win32com.client": mock_win32}):
            handle = ops.insert_block(
                block_name="CB_3P",
                x=100.0,
                y=200.0,
                layer="ELEC-SYMBOL",
            )

        assert handle == "A1B2C3"
        mock_model_space.InsertBlock.assert_called_once()

    def test_insert_block_sets_layer(self, mock_autocad_connection):
        """insert_block sets block_ref.Layer to the provided layer name."""
        from autocad.drawing_ops import DrawingOps

        _, mock_doc, mock_model_space = mock_autocad_connection

        mock_block_ref = MagicMock()
        mock_block_ref.Handle = "HANDLE1"
        mock_block_ref.HasAttributes = False
        mock_model_space.InsertBlock.return_value = mock_block_ref

        ops = DrawingOps()
        mock_win32 = _make_win32_mock()
        with patch.dict(sys.modules, {"win32com": mock_win32, "win32com.client": mock_win32}):
            ops.insert_block("TR_2W", 0.0, 0.0, layer="ELEC-TRANSFORMER")

        assert mock_block_ref.Layer == "ELEC-TRANSFORMER"

    def test_insert_block_with_attributes(self, mock_autocad_connection):
        """insert_block sets attribute TextString when block has attributes."""
        from autocad.drawing_ops import DrawingOps

        _, mock_doc, mock_model_space = mock_autocad_connection

        mock_attrib = MagicMock()
        mock_attrib.TagString = "LABEL"

        mock_block_ref = MagicMock()
        mock_block_ref.Handle = "ATTR_HANDLE"
        mock_block_ref.HasAttributes = True
        mock_block_ref.GetAttributes.return_value = [mock_attrib]
        mock_model_space.InsertBlock.return_value = mock_block_ref

        ops = DrawingOps()
        mock_win32 = _make_win32_mock()
        with patch.dict(sys.modules, {"win32com": mock_win32, "win32com.client": mock_win32}):
            ops.insert_block("CB_3P", 0.0, 0.0, attributes={"LABEL": "QF1"})

        assert mock_attrib.TextString == "QF1"

    def test_insert_block_raises_on_com_failure(self, mock_autocad_connection):
        """RuntimeError is raised when InsertBlock throws an exception."""
        from autocad.drawing_ops import DrawingOps

        _, mock_doc, mock_model_space = mock_autocad_connection
        mock_model_space.InsertBlock.side_effect = Exception("block not found")

        ops = DrawingOps()
        mock_win32 = _make_win32_mock()
        with patch.dict(sys.modules, {"win32com": mock_win32, "win32com.client": mock_win32}):
            with pytest.raises(RuntimeError, match="插入图块失败"):
                ops.insert_block("MISSING", 0.0, 0.0)

    def test_delete_entity_returns_true_on_success(self, mock_autocad_connection):
        """delete_entity returns True when entity is found and deleted."""
        from autocad.drawing_ops import DrawingOps

        _, mock_doc, _ = mock_autocad_connection
        mock_entity = MagicMock()
        mock_doc.HandleToObject.return_value = mock_entity

        ops = DrawingOps()
        result = ops.delete_entity("HANDLE_XYZ")

        assert result is True
        mock_entity.Delete.assert_called_once()

    def test_delete_entity_returns_false_on_failure(self, mock_autocad_connection):
        """delete_entity returns False (no exception) when handle is invalid."""
        from autocad.drawing_ops import DrawingOps

        _, mock_doc, _ = mock_autocad_connection
        mock_doc.HandleToObject.side_effect = Exception("invalid handle")

        ops = DrawingOps()
        result = ops.delete_entity("INVALID_HANDLE")

        assert result is False

    def test_move_entity_returns_true(self, mock_autocad_connection):
        """move_entity returns True when entity.Move succeeds."""
        from autocad.drawing_ops import DrawingOps

        _, mock_doc, _ = mock_autocad_connection
        mock_entity = MagicMock()
        mock_doc.HandleToObject.return_value = mock_entity

        ops = DrawingOps()
        mock_win32 = _make_win32_mock()
        with patch.dict(sys.modules, {"win32com": mock_win32, "win32com.client": mock_win32}):
            result = ops.move_entity("H1", 0.0, 0.0, 100.0, 200.0)

        assert result is True
        mock_entity.Move.assert_called_once()

    def test_get_all_entities_returns_list(self, mock_autocad_connection):
        """get_all_entities returns a list of entity dicts."""
        from autocad.drawing_ops import DrawingOps

        _, mock_doc, mock_model_space = mock_autocad_connection

        mock_entity = MagicMock()
        mock_entity.Handle = "E1"
        mock_entity.EntityName = "AcDbBlockReference"
        mock_entity.Layer = "ELEC-SYMBOL"
        mock_entity.Visible = True
        mock_entity.InsertionPoint = [10.0, 20.0, 0.0]
        mock_model_space.Count = 1
        mock_model_space.Item.return_value = mock_entity

        ops = DrawingOps()
        entities = ops.get_all_entities()

        assert len(entities) == 1
        assert entities[0]["handle"] == "E1"
        assert entities[0]["layer"] == "ELEC-SYMBOL"
        assert entities[0]["x"] == 10.0
        assert entities[0]["y"] == 20.0

    def test_get_all_entities_returns_empty_on_error(self, mock_autocad_connection):
        """get_all_entities returns [] when model_space raises an exception."""
        from autocad.drawing_ops import DrawingOps

        _, mock_doc, mock_model_space = mock_autocad_connection
        type(mock_model_space).Count = PropertyMock(side_effect=Exception("COM error"))

        ops = DrawingOps()
        entities = ops.get_all_entities()

        assert entities == []

    def test_draw_line_returns_handle(self, mock_autocad_connection):
        """draw_line returns the line Handle string."""
        from autocad.drawing_ops import DrawingOps

        _, mock_doc, mock_model_space = mock_autocad_connection
        mock_line = MagicMock()
        mock_line.Handle = "LINE_HANDLE"
        mock_model_space.AddLine.return_value = mock_line

        ops = DrawingOps()
        mock_win32 = _make_win32_mock()
        with patch.dict(sys.modules, {"win32com": mock_win32, "win32com.client": mock_win32}):
            handle = ops.draw_line(0.0, 0.0, 100.0, 100.0, layer="ELEC-WIRE")

        assert handle == "LINE_HANDLE"
        assert mock_line.Layer == "ELEC-WIRE"

    def test_draw_line_raises_on_failure(self, mock_autocad_connection):
        """draw_line raises RuntimeError when AddLine fails."""
        from autocad.drawing_ops import DrawingOps

        _, mock_doc, mock_model_space = mock_autocad_connection
        mock_model_space.AddLine.side_effect = Exception("layer locked")

        ops = DrawingOps()
        mock_win32 = _make_win32_mock()
        with patch.dict(sys.modules, {"win32com": mock_win32, "win32com.client": mock_win32}):
            with pytest.raises(RuntimeError, match="绘制连线失败"):
                ops.draw_line(0.0, 0.0, 100.0, 100.0)
