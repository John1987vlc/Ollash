"""Unit tests for the Signature-Only RAG helpers in phase_context.py.

Tests cover _extract_signatures, _extract_signatures_regex, and the
signatures_only parameter of PhaseContext.select_related_files().
No real I/O — file contents are provided as in-memory strings.
"""

import pytest
from unittest.mock import MagicMock

from backend.agents.auto_agent_phases.phase_context import (
    _extract_signatures,
)
from backend.utils.domains.auto_generation.utilities.signature_extractor import (
    extract_signatures_regex as _extract_signatures_regex,
)


@pytest.mark.unit
class TestExtractSignaturesPython:
    """Tests for AST-based Python signature extraction."""

    def test_extracts_function_signature(self):
        code = "def foo(x: int, y: str) -> bool:\n    return True\n"
        result = _extract_signatures(code, "module.py")
        assert "def foo(x: int, y: str) -> bool:" in result

    def test_extracts_class_signature(self):
        code = "class MyClass(Base):\n    pass\n"
        result = _extract_signatures(code, "models.py")
        assert "class MyClass(Base):" in result

    def test_extracts_async_function(self):
        code = "async def fetch(url: str) -> dict:\n    pass\n"
        result = _extract_signatures(code, "client.py")
        assert "async def fetch(url: str) -> dict:" in result

    def test_multiple_functions_all_extracted(self):
        code = "def alpha() -> None:\n    pass\n\ndef beta(x: int) -> str:\n    return str(x)\n"
        result = _extract_signatures(code, "utils.py")
        assert "def alpha" in result
        assert "def beta" in result

    def test_broken_python_falls_back_to_regex_or_snippet(self):
        # Intentionally invalid Python — should not raise
        code = "def broken(\n    return 1\nclass NoColon\n"
        result = _extract_signatures(code, "broken.py")
        # Fallback should return something (either regex hits or first 500 chars)
        assert isinstance(result, str)

    def test_empty_file_returns_snippet(self):
        result = _extract_signatures("", "empty.py")
        # Empty content → content[:500] is empty string
        assert result == ""

    def test_non_python_ext_uses_regex(self):
        # JavaScript — should not attempt AST
        code = "function greet(name) { return 'Hello ' + name; }"
        result = _extract_signatures(code, "app.js")
        assert isinstance(result, str)


@pytest.mark.unit
class TestExtractSignaturesRegex:
    """Tests for regex-based signature extraction for non-Python languages."""

    def test_javascript_function(self):
        code = "function greet(name) {\n    return name;\n}"
        lines = _extract_signatures_regex(code, ".js")
        assert any("function greet" in ln for ln in lines)

    def test_javascript_arrow_function(self):
        code = "const handler = async (req) => {\n    return req;\n}"
        lines = _extract_signatures_regex(code, ".js")
        assert any("handler" in ln for ln in lines)

    def test_typescript_class(self):
        code = "export class UserService extends BaseService {\n}"
        lines = _extract_signatures_regex(code, ".ts")
        assert any("UserService" in ln for ln in lines)

    def test_go_function(self):
        code = "func (s *Server) Start(port int) error {"
        lines = _extract_signatures_regex(code, ".go")
        assert any("Start" in ln for ln in lines)

    def test_unknown_extension_uses_fallback_pattern(self):
        code = "def something(x, y):"
        lines = _extract_signatures_regex(code, ".xyz")
        assert any("something" in ln for ln in lines)

    def test_empty_code_returns_empty_list(self):
        lines = _extract_signatures_regex("", ".py")
        assert lines == []


@pytest.mark.unit
class TestSelectRelatedFilesSignaturesOnly:
    """Tests for signatures_only parameter of PhaseContext.select_related_files()."""

    @pytest.fixture()
    def mock_context(self):
        """Build a minimal PhaseContext-like mock with the real select_related_files logic."""
        # We patch the class at the constructor level but call the real method
        ctx = MagicMock()
        ctx.rag_context_selector.select_relevant_files.side_effect = Exception("RAG unavailable")
        ctx.logger.info = MagicMock()
        return ctx

    def test_signatures_only_returns_shorter_content(self):
        """When signatures_only=True the returned content must be ≤ original length."""
        from backend.agents.auto_agent_phases.phase_context import PhaseContext

        generated_files = {
            "src/utils.py": (
                "def compute(x: int) -> int:\n"
                "    # lots of implementation detail\n"
                "    result = x * 2 + 1\n"
                "    return result\n"
            )
        }

        ctx = MagicMock()
        ctx.rag_context_selector.select_relevant_files.side_effect = Exception("no RAG")
        ctx.logger.info = MagicMock()

        # Call the real method bound to a mock instance
        result = PhaseContext.select_related_files(
            ctx,
            target_path="src/main.py",
            generated_files=generated_files,
            max_files=8,
            signatures_only=True,
        )

        assert "src/utils.py" in result
        # Signature should be much shorter than full file
        full_len = len(generated_files["src/utils.py"])
        sig_len = len(result["src/utils.py"])
        assert sig_len < full_len

    def test_signatures_only_false_returns_full_content(self):
        """When signatures_only=False (default) full content is returned."""
        from backend.agents.auto_agent_phases.phase_context import PhaseContext

        content = "def foo():\n    return 42\n" * 10  # 240+ chars
        generated_files = {"src/foo.py": content}

        ctx = MagicMock()
        ctx.rag_context_selector.select_relevant_files.side_effect = Exception("no RAG")
        ctx.logger.info = MagicMock()

        result = PhaseContext.select_related_files(
            ctx,
            target_path="src/main.py",
            generated_files=generated_files,
            signatures_only=False,
        )
        assert result["src/foo.py"] == content

    def test_empty_generated_files_returns_empty(self):
        from backend.agents.auto_agent_phases.phase_context import PhaseContext

        ctx = MagicMock(spec=PhaseContext)
        result = PhaseContext.select_related_files(ctx, target_path="x.py", generated_files={}, signatures_only=True)
        assert result == {}
