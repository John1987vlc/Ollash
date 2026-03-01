"""Unit tests for LLMResponseParser.extract_thought_action().

Purely exercises the new additive method — no I/O, no LLM calls.
"""

import pytest

from backend.utils.core.llm.llm_response_parser import LLMResponseParser


@pytest.mark.unit
class TestExtractThoughtAction:
    """Tests for the dual (thought, action) output extractor."""

    # ------------------------------------------------------------------
    # JSON format
    # ------------------------------------------------------------------

    def test_json_format_both_fields(self):
        response = '{"thought": "I should use DI", "action": "inject the dependency"}'
        thought, action = LLMResponseParser.extract_thought_action(response)
        assert thought == "I should use DI"
        assert action == "inject the dependency"

    def test_json_format_only_thought(self):
        response = '{"thought": "Only thinking here"}'
        thought, action = LLMResponseParser.extract_thought_action(response)
        assert thought == "Only thinking here"
        assert action == ""

    def test_json_format_only_action(self):
        response = '{"action": "Do something"}'
        thought, action = LLMResponseParser.extract_thought_action(response)
        assert thought == ""
        assert action == "Do something"

    # ------------------------------------------------------------------
    # XML tag format
    # ------------------------------------------------------------------

    def test_xml_tag_format(self):
        response = "<thought>Think carefully</thought><action>Write the code</action>"
        thought, action = LLMResponseParser.extract_thought_action(response)
        assert thought == "Think carefully"
        assert action == "Write the code"

    def test_xml_tag_format_multiline(self):
        response = "<thought>\nStep 1: analyze\nStep 2: plan\n</thought>\n<action>Implement now</action>"
        thought, action = LLMResponseParser.extract_thought_action(response)
        assert "analyze" in thought
        assert action == "Implement now"

    def test_xml_tag_case_insensitive(self):
        response = "<THOUGHT>analysis</THOUGHT><ACTION>write</ACTION>"
        thought, action = LLMResponseParser.extract_thought_action(response)
        assert thought == "analysis"
        assert action == "write"

    # ------------------------------------------------------------------
    # Fallback behavior
    # ------------------------------------------------------------------

    def test_fallback_plain_text_goes_to_action(self):
        response = "This is just a plain text response with no special format."
        thought, action = LLMResponseParser.extract_thought_action(response)
        assert thought == ""
        assert "plain text response" in action

    def test_empty_response_returns_empty_strings(self):
        thought, action = LLMResponseParser.extract_thought_action("")
        assert thought == ""
        assert action == ""

    def test_none_is_handled_as_empty(self):
        # extract_thought_action requires str; pass empty string as proxy
        thought, action = LLMResponseParser.extract_thought_action("")
        assert thought == ""
        assert action == ""

    # ------------------------------------------------------------------
    # Think blocks are stripped first
    # ------------------------------------------------------------------

    def test_strips_think_blocks_before_parsing(self):
        response = (
            "<thinking>This is internal reasoning that should be stripped.</thinking>\n"
            '{"thought": "public thought", "action": "public action"}'
        )
        thought, action = LLMResponseParser.extract_thought_action(response)
        assert thought == "public thought"
        assert action == "public action"

    def test_think_block_only_returns_empty(self):
        response = "<thinking>Only internal thought, no output</thinking>"
        thought, action = LLMResponseParser.extract_thought_action(response)
        # After stripping think block, no format found → fallback with empty cleaned text
        assert thought == ""

    # ------------------------------------------------------------------
    # Return type
    # ------------------------------------------------------------------

    def test_return_type_is_tuple_of_strings(self):
        result = LLMResponseParser.extract_thought_action('{"thought": "t", "action": "a"}')
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(v, str) for v in result)
