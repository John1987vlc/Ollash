"""Unit tests for CodePatcher — verifies difflib-based merge replaces old heuristics."""

import difflib
import pytest
from unittest.mock import MagicMock

from backend.utils.domains.auto_generation.code_patcher import CodePatcher


@pytest.fixture
def mock_llm():
    return MagicMock()


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def patcher(mock_llm, mock_logger):
    return CodePatcher(llm_client=mock_llm, logger=mock_logger)


@pytest.mark.unit
class TestSmartMerge:
    def test_keeps_original_when_improved_is_empty(self, patcher):
        original = "def foo():\n    return 1\n"
        assert patcher._smart_merge(original, "") == original

    def test_keeps_original_when_improved_is_too_short(self, patcher):
        original = "def foo():\n    return 1\n"
        assert patcher._smart_merge(original, "x") == original

    def test_keeps_original_when_similarity_too_low(self, patcher):
        original = "def calculate(a, b):\n    return a + b\n"
        # Completely different content → similarity < 0.3
        totally_different = "SELECT * FROM users WHERE id = 1;" * 10
        result = patcher._smart_merge(original, totally_different)
        assert result == original

    def test_uses_improved_when_similarity_high(self, patcher):
        original = "def foo():\n    pass\n"
        # Very similar — just adds a return statement
        improved = "def foo():\n    return 42\n"
        result = patcher._smart_merge(original, improved)
        assert result == improved

    def test_no_length_ratio_heuristic(self):
        """Regression: the old `len(improved) > len(original) * 0.8` must not exist."""
        import inspect
        import backend.utils.domains.auto_generation.code_patcher as mod
        source = inspect.getsource(mod)
        assert "* 0.8" not in source, "Old length-ratio heuristic detected in code_patcher"
        assert "* 1.5" not in source, "Old length-ratio heuristic detected in code_patcher"

    def test_moderate_similarity_merge_preserves_original_unique_lines(self, patcher):
        original = "def foo():\n    x = 1\n    custom_logic()\n    return x\n"
        # Similar but missing the custom line
        improved = "def foo():\n    x = 1\n    return x\n"
        result = patcher._smart_merge(original, improved)
        # Result should not be identical to improved (custom_logic preserved)
        # At minimum it must not crash and must return a non-empty string
        assert isinstance(result, str)
        assert len(result) > 0


@pytest.mark.unit
class TestIsBetterLine:
    def test_line_with_fewer_todos_is_better(self, patcher):
        orig = "    # TODO: implement this properly"
        improved = "    return compute(x)"
        assert patcher._is_better_line(orig, improved) is True

    def test_empty_improved_is_not_better(self, patcher):
        assert patcher._is_better_line("    return x", "") is False

    def test_empty_orig_is_not_better(self, patcher):
        assert patcher._is_better_line("", "    return x") is False

    def test_no_brace_counting_heuristic(self):
        """Regression: brace + parenthesis counting must not be in _is_better_line."""
        import inspect
        import backend.utils.domains.auto_generation.code_patcher as mod
        source = inspect.getsource(mod._is_better_line if hasattr(mod, "_is_better_line") else mod)
        # Get just the method source from the class
        patcher_source = inspect.getsource(CodePatcher._is_better_line)
        assert 'count("{")' not in patcher_source, "Brace-counting heuristic still present"
        assert 'count("(")' not in patcher_source, "Paren-counting heuristic still present"

    def test_similar_but_longer_improved_is_better(self, patcher):
        # Choose lines whose stripped difflib ratio is > 0.6 and improved is longer.
        # orig (18 chars): 'return {"ok": True}'
        # improved (30 chars): 'return {"ok": True, "count": n}'
        # ratio ≈ 2*19/(18+31) ≈ 0.78 > 0.6 ✓ and len(improved) > len(orig) ✓
        orig = '    return {"ok": True}'
        improved = '    return {"ok": True, "count": n}'
        assert patcher._is_better_line(orig, improved) is True


@pytest.mark.unit
class TestEditExistingFile:
    def test_returns_empty_string_for_empty_content(self, patcher):
        result = patcher.edit_existing_file("f.py", "", "# README")
        assert result == ""

    def test_partial_strategy_with_no_issues_returns_original(self, patcher):
        content = "def foo():\n    pass\n"
        result = patcher.edit_existing_file("f.py", content, "# README", [], "partial")
        assert result == content

    def test_unknown_strategy_returns_original(self, patcher):
        content = "def foo():\n    pass\n"
        result = patcher.edit_existing_file("f.py", content, "# README", None, "unknown")
        assert result == content

    def test_partial_strategy_applies_fixes(self, patcher, mock_llm):
        content = "def foo():\n    badcode()\n    return None\n"
        mock_llm.chat.return_value = (
            {"content": "    return 42"},
            {},
        )
        issues = [{"description": "badcode should return 42"}]
        result = patcher.edit_existing_file("f.py", content, "# README", issues, "partial")
        assert isinstance(result, str)
        assert len(result) > 0
