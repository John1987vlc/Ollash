"""Unit tests for Opt 6: active shadow validation in ShadowEvaluator.

Tests cover _check_format() and active_shadow_validate().
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from backend.utils.core.analysis.shadow_evaluator import ShadowEvaluator


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def shadow():
    logger = MagicMock()
    event_publisher = MagicMock()
    log_dir = Path("/tmp/shadow_logs")
    return ShadowEvaluator(logger=logger, event_publisher=event_publisher, log_dir=log_dir)


@pytest.fixture
def mock_llm():
    """LLM manager mock that returns a nano_format_corrector response."""
    llm = MagicMock()
    client = MagicMock()
    llm.get_client.return_value = client
    client.model = "ministral-3:3b"
    return llm


# ---------------------------------------------------------------------------
# Tests: _check_format()
# ---------------------------------------------------------------------------


class TestCheckFormat:
    @pytest.mark.unit
    def test_valid_python_returns_empty_string(self, shadow):
        code = "def f(x):\n    return x + 1\n"
        assert shadow._check_format(code, "python") == ""

    @pytest.mark.unit
    def test_invalid_python_returns_error(self, shadow):
        code = "def f(:\n    return 1"  # Missing closing paren
        error = shadow._check_format(code, "python")
        assert error != ""
        assert "SyntaxError" in error or "syntax" in error.lower()

    @pytest.mark.unit
    def test_py_extension_treated_as_python(self, shadow):
        code = "def f():\n    return 1\n"
        assert shadow._check_format(code, ".py") == ""

    @pytest.mark.unit
    def test_valid_json_returns_empty_string(self, shadow):
        code = '{"key": "value", "number": 42}'
        assert shadow._check_format(code, "json") == ""

    @pytest.mark.unit
    def test_invalid_json_returns_error(self, shadow):
        code = "{invalid json}"
        error = shadow._check_format(code, "json")
        assert error != ""

    @pytest.mark.unit
    def test_balanced_js_braces_returns_empty(self, shadow):
        code = "function f() { return 1; }"
        assert shadow._check_format(code, "javascript") == ""

    @pytest.mark.unit
    def test_unbalanced_js_braces_returns_error(self, shadow):
        code = "function f() { return 1; "  # Missing closing brace
        error = shadow._check_format(code, "javascript")
        assert error != ""
        assert "brace" in error.lower()

    @pytest.mark.unit
    def test_ts_extension_treated_as_typescript(self, shadow):
        code = "function f(): number { return 1; }"
        assert shadow._check_format(code, "ts") == ""

    @pytest.mark.unit
    def test_unknown_language_always_passes(self, shadow):
        # Go, Rust, etc. always return empty (no checker available)
        assert shadow._check_format("anything", "go") == ""
        assert shadow._check_format("anything", "rust") == ""
        assert shadow._check_format("malformed {{{ text", "ruby") == ""


# ---------------------------------------------------------------------------
# Tests: active_shadow_validate()
# ---------------------------------------------------------------------------


class TestActiveShadowValidate:
    @pytest.mark.unit
    def test_valid_code_returns_unchanged(self, shadow, mock_llm):
        code = "def f():\n    return 1\n"
        # The new logic calls nano_reviewer for code that passes basic checks
        mock_llm.get_client.return_value.chat.return_value = (
            {"content": '{"has_errors": false, "errors": []}'},
            {},
        )
        result, repaired = shadow.active_shadow_validate("f.py", code, "python", mock_llm, MagicMock())
        assert result == code
        assert repaired is False
        # Should have called get_client('nano_reviewer')
        mock_llm.get_client.assert_called_with("nano_reviewer")

    @pytest.mark.unit
    def test_invalid_python_triggers_nano_reviewer(self, shadow, mock_llm):
        broken = "def f(:\n    return 1"
        fixed = "def f():\n    return 1\n"
        mock_llm.get_client.return_value.chat.return_value = (
            {"content": f"<code_fixed>{fixed}</code_fixed>"},
            {},
        )
        with MagicMock() as mock_prompts:
            import backend.utils.domains.auto_generation.prompt_templates as pt

            orig = pt.AutoGenPrompts.nano_format_corrector

            def _sync_nano(**kwargs):
                return ("sys", "usr")

            pt.AutoGenPrompts.nano_format_corrector = staticmethod(_sync_nano)
            try:
                result, repaired = shadow.active_shadow_validate("f.py", broken, "python", mock_llm, MagicMock())
            finally:
                pt.AutoGenPrompts.nano_format_corrector = orig

        assert repaired is True
        assert "def f():" in result

    @pytest.mark.unit
    def test_nano_reviewer_failure_returns_original(self, shadow, mock_llm):
        broken = "def f(:\n    pass"
        mock_llm.get_client.return_value.chat.side_effect = RuntimeError("network down")

        import backend.utils.domains.auto_generation.prompt_templates as pt

        orig = pt.AutoGenPrompts.nano_format_corrector

        def _sync_nano(**kwargs):
            return ("sys", "usr")

        pt.AutoGenPrompts.nano_format_corrector = staticmethod(_sync_nano)
        try:
            result, repaired = shadow.active_shadow_validate("f.py", broken, "python", mock_llm, MagicMock())
        finally:
            pt.AutoGenPrompts.nano_format_corrector = orig

        assert result == broken
        assert repaired is False

    @pytest.mark.unit
    def test_nano_repair_that_still_has_errors_returns_original(self, shadow, mock_llm):
        """If the nano model returns still-broken code, return original."""
        broken = "def f(:\n    return 1"
        still_broken = "def g(:\n    return 2"  # Also invalid Python
        mock_llm.get_client.return_value.chat.return_value = (
            {"content": f"<code_fixed>{still_broken}</code_fixed>"},
            {},
        )
        import backend.utils.domains.auto_generation.prompt_templates as pt

        orig = pt.AutoGenPrompts.nano_format_corrector

        def _sync_nano(**kwargs):
            return ("sys", "usr")

        pt.AutoGenPrompts.nano_format_corrector = staticmethod(_sync_nano)
        try:
            result, repaired = shadow.active_shadow_validate("f.py", broken, "python", mock_llm, MagicMock())
        finally:
            pt.AutoGenPrompts.nano_format_corrector = orig

        # Repair did not fix the issue, should return original
        assert result == broken
        assert repaired is False

    @pytest.mark.unit
    def test_valid_json_not_repaired(self, shadow, mock_llm):
        code = '{"ok": true}'
        result, repaired = shadow.active_shadow_validate("data.json", code, "json", mock_llm, MagicMock())
        assert result == code
        assert repaired is False

    @pytest.mark.unit
    def test_shadow_log_recorded_on_repair(self, shadow, mock_llm):
        broken = "def f(:\n    return 1"
        fixed = "def f():\n    return 1\n"
        mock_llm.get_client.return_value.chat.return_value = (
            {"content": f"<code_fixed>{fixed}</code_fixed>"},
            {},
        )
        initial_log_count = len(shadow._logs)

        import backend.utils.domains.auto_generation.prompt_templates as pt

        orig = pt.AutoGenPrompts.nano_format_corrector

        def _sync_nano(**kwargs):
            return ("sys", "usr")

        pt.AutoGenPrompts.nano_format_corrector = staticmethod(_sync_nano)
        try:
            shadow.active_shadow_validate("f.py", broken, "python", mock_llm, MagicMock())
        finally:
            pt.AutoGenPrompts.nano_format_corrector = orig

        assert len(shadow._logs) == initial_log_count + 1
        assert shadow._logs[-1].critic_correction is not None
