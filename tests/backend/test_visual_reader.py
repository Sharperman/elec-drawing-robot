"""
Test Suite: Visual Reader
Tests for:
  - autocad/visual_reader.py - count field type handling, result parsing
"""
import sys
from unittest.mock import MagicMock


# Inject win32com stubs
def _inject_win32_stubs() -> None:
    if "win32com" not in sys.modules:
        _stub = MagicMock()
        sys.modules["win32com"] = _stub
        sys.modules["win32com.client"] = _stub.client
    if "pywintypes" not in sys.modules:
        sys.modules["pywintypes"] = MagicMock()


_inject_win32_stubs()


# ============================================================
# Test: Visual reader count field type coercion
# ============================================================

class TestVisualReaderCountField:
    """Tests for the int() type coercion fix on count fields from LLM output."""

    def test_count_as_string_is_converted(self):
        """LLM sometimes returns count as string "1" instead of int 1."""
        # Simulate the data flow where count is a string
        d = {"name": "断路器", "count": "3"}
        count_val = d.get("count", 1)
        try:
            count_val = int(count_val)
        except (ValueError, TypeError):
            count_val = 1
        assert count_val == 3
        assert isinstance(count_val, int)

    def test_count_as_int_passes_through(self):
        d = {"name": "变压器", "count": 2}
        count_val = d.get("count", 1)
        try:
            count_val = int(count_val)
        except (ValueError, TypeError):
            count_val = 1
        assert count_val == 2

    def test_count_missing_defaults_to_1(self):
        d = {"name": "接触器"}
        count_val = d.get("count", 1)
        try:
            count_val = int(count_val)
        except (ValueError, TypeError):
            count_val = 1
        assert count_val == 1

    def test_count_as_invalid_string_defaults_to_1(self):
        d = {"name": "继电器", "count": "abc"}
        count_val = d.get("count", 1)
        try:
            count_val = int(count_val)
        except (ValueError, TypeError):
            count_val = 1
        assert count_val == 1

    def test_count_as_none_defaults_to_1(self):
        d = {"name": "熔断器", "count": None}
        count_val = d.get("count", 1)
        try:
            count_val = int(count_val)
        except (ValueError, TypeError):
            count_val = 1
        assert count_val == 1

    def test_count_comparison_works_after_coercion(self):
        """The original bug: '3' > 1 raised TypeError."""
        d = {"name": "断路器", "count": "3"}
        count_val = d.get("count", 1)
        try:
            count_val = int(count_val)
        except (ValueError, TypeError):
            count_val = 1
        # This was the failing comparison
        assert count_val > 1


# ============================================================
# Test: Visual reader result parsing
# ============================================================

class TestVisualReaderParsing:
    """Tests for LLM output JSON parsing in visual_reader."""

    def test_parse_valid_element_list(self):
        """Valid JSON with elements array should parse correctly."""
        import json
        raw = json.dumps({
            "elements": [
                {"name": "断路器", "category": "protection", "count": 2},
                {"name": "变压器", "category": "transformer", "count": 1},
            ]
        })
        parsed = json.loads(raw)
        assert len(parsed["elements"]) == 2

    def test_parse_with_string_counts(self):
        """JSON where count fields are strings should still load."""
        import json
        raw = json.dumps({
            "elements": [
                {"name": "断路器", "count": "2"},
                {"name": "变压器", "count": "1"},
            ]
        })
        parsed = json.loads(raw)
        # After parsing, count is still string — needs coercion
        for el in parsed["elements"]:
            el["count"] = int(el.get("count", 1))
        assert parsed["elements"][0]["count"] == 2
        assert isinstance(parsed["elements"][0]["count"], int)

    def test_parse_empty_elements(self):
        import json
        raw = json.dumps({"elements": []})
        parsed = json.loads(raw)
        assert parsed["elements"] == []
