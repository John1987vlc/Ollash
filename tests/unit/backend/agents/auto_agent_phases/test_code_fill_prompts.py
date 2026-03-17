"""Unit tests for C# system prompts in CodeFillPhase — Fix 3."""

import pytest

from backend.agents.auto_agent_phases.code_fill_phase import (
    _SYSTEM_BY_EXT,
    _SYSTEM_BY_EXT_SMALL,
    _SYSTEM_CSHARP,
)


@pytest.mark.unit
class TestCsharpSystemPrompts:
    def test_large_prompt_warns_against_remove_async(self):
        """_SYSTEM_CSHARP must mention RemoveAsync so the LLM knows NOT to use it."""
        assert "RemoveAsync" in _SYSTEM_CSHARP

    def test_large_prompt_covers_add_controllers(self):
        assert "AddControllers" in _SYSTEM_CSHARP

    def test_large_prompt_covers_map_controllers(self):
        assert "MapControllers" in _SYSTEM_CSHARP

    def test_large_prompt_covers_ef_core_remove(self):
        """Must explain that Remove() (not RemoveAsync) is the correct EF Core method."""
        assert "Remove(" in _SYSTEM_CSHARP or "Remove(entity)" in _SYSTEM_CSHARP

    def test_large_prompt_covers_http_verb_guidance(self):
        assert "HttpGet" in _SYSTEM_CSHARP
        assert "HttpPost" in _SYSTEM_CSHARP

    def test_large_prompt_in_ext_map(self):
        assert ".cs" in _SYSTEM_BY_EXT
        assert _SYSTEM_BY_EXT[".cs"] is _SYSTEM_CSHARP

    def test_small_prompt_warns_against_remove_async(self):
        small = _SYSTEM_BY_EXT_SMALL[".cs"]
        assert "RemoveAsync" in small

    def test_small_prompt_covers_add_controllers(self):
        small = _SYSTEM_BY_EXT_SMALL[".cs"]
        assert "AddControllers" in small

    def test_small_prompt_covers_http_get_read_only(self):
        small = _SYSTEM_BY_EXT_SMALL[".cs"]
        assert "HttpGet" in small
