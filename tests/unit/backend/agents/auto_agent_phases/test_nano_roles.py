"""Unit tests for Nano Role prompts in AutoGenPrompts.

Verifies that nano_planner, nano_coder, and nano_reviewer methods return
properly formatted (system, user) tuples with variables substituted.
No YAML file I/O — the PromptLoader is mocked.
"""

import pytest
from unittest.mock import patch, AsyncMock

from backend.utils.domains.auto_generation.prompt_templates import AutoGenPrompts


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def patch_prompt_loader():
    """Mock PromptLoader so no YAML file I/O occurs during unit tests."""
    with patch.object(AutoGenPrompts, "_loader") as mock_loader, patch.object(AutoGenPrompts, "_repository", None):
        # Return a dict matching the nano_roles.yaml structure
        mock_loader.load_prompt = AsyncMock(
            return_value={
                "nano_planner_prompt": {
                    "system": "You are a file list generator. Output JSON only.",
                    "user": "Project name: {project_name}\nDescription: {project_description}\nOutput the JSON array only.",
                },
                "nano_coder_prompt": {
                    "system": "You are a single-function code writer.",
                    "user": (
                        "Function name: {function_name}\nSignature: {signature}\n"
                        "Docstring: {docstring}\nContext: {context_snippet}\nOutput function body."
                    ),
                },
                "nano_reviewer_prompt": {
                    "system": "You are a syntax and indentation checker.",
                    "user": "Language: {language}\nCode:\n```\n{code}\n```\nOutput JSON only.",
                },
            }
        )
        yield mock_loader


# ---------------------------------------------------------------------------
# nano_planner
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestNanoPlanner:
    async def test_returns_tuple_of_two_strings(self):
        system, user = await AutoGenPrompts.nano_planner("MyProject", "A REST API")
        assert isinstance(system, str)
        assert isinstance(user, str)

    async def test_project_name_substituted_in_user(self):
        _, user = await AutoGenPrompts.nano_planner("Ollash", "An agent platform")
        assert "Ollash" in user

    async def test_project_description_substituted_in_user(self):
        _, user = await AutoGenPrompts.nano_planner("X", "Build a FastAPI service")
        assert "Build a FastAPI service" in user

    async def test_no_unresolved_placeholders(self):
        _, user = await AutoGenPrompts.nano_planner("P", "D")
        assert "{project_name}" not in user
        assert "{project_description}" not in user

    async def test_system_prompt_not_empty(self):
        system, _ = await AutoGenPrompts.nano_planner("P", "D")
        assert len(system) > 0


# ---------------------------------------------------------------------------
# nano_coder
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestNanoCoder:
    async def test_returns_tuple_of_two_strings(self):
        system, user = await AutoGenPrompts.nano_coder(
            function_name="compute",
            signature="def compute(x: int) -> int:",
            docstring="Return double of x.",
        )
        assert isinstance(system, str)
        assert isinstance(user, str)

    async def test_function_name_in_user(self):
        _, user = await AutoGenPrompts.nano_coder("my_func", "def my_func():", "Does X.")
        assert "my_func" in user

    async def test_signature_in_user(self):
        _, user = await AutoGenPrompts.nano_coder("f", "def f(x: int) -> bool:", "Checks x.")
        assert "def f(x: int) -> bool:" in user

    async def test_docstring_in_user(self):
        _, user = await AutoGenPrompts.nano_coder("f", "def f():", "Returns True always.")
        assert "Returns True always." in user

    async def test_no_context_uses_default(self):
        _, user = await AutoGenPrompts.nano_coder("f", "def f():", "doc")
        assert "(no context available)" in user

    async def test_context_snippet_substituted(self):
        _, user = await AutoGenPrompts.nano_coder("f", "def f():", "doc", "x = 1\n")
        assert "x = 1" in user

    async def test_no_unresolved_placeholders(self):
        _, user = await AutoGenPrompts.nano_coder("f", "sig", "doc", "ctx")
        for placeholder in ["{function_name}", "{signature}", "{docstring}", "{context_snippet}"]:
            assert placeholder not in user


# ---------------------------------------------------------------------------
# nano_reviewer
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestNanoReviewer:
    async def test_returns_tuple_of_two_strings(self):
        system, user = await AutoGenPrompts.nano_reviewer("Python", "def foo():\n    pass\n")
        assert isinstance(system, str)
        assert isinstance(user, str)

    async def test_language_substituted_in_user(self):
        _, user = await AutoGenPrompts.nano_reviewer("JavaScript", "function f() {}")
        assert "JavaScript" in user

    async def test_code_substituted_in_user(self):
        code = "def x():\n    return 1\n"
        _, user = await AutoGenPrompts.nano_reviewer("Python", code)
        assert "def x():" in user

    async def test_no_unresolved_placeholders(self):
        _, user = await AutoGenPrompts.nano_reviewer("Go", "func f() {}")
        assert "{language}" not in user
        assert "{code}" not in user

    async def test_system_mentions_syntax(self):
        system, _ = await AutoGenPrompts.nano_reviewer("Python", "x = 1")
        assert len(system) > 0
