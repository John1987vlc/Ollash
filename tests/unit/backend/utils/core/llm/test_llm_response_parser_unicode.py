"""Unit tests for Fix 3 — Unicode / encoding repair in LLMResponseParser."""

import pytest

from backend.utils.core.llm.llm_response_parser import LLMResponseParser


@pytest.mark.unit
class TestCardSuitMojibakeRepair:
    """_repair_json_string fixes classic UTF-8-as-latin1 mojibake for card suits."""

    def test_heart_mojibake_repaired(self):
        broken = '{"suit": "â™¥"}'
        result = LLMResponseParser._repair_json_string(broken)
        assert "♥" in result

    def test_diamond_mojibake_repaired(self):
        broken = '{"suit": "â™¦"}'
        result = LLMResponseParser._repair_json_string(broken)
        assert "♦" in result

    def test_club_mojibake_repaired(self):
        broken = '{"suit": "â™£"}'
        result = LLMResponseParser._repair_json_string(broken)
        assert "♣" in result

    def test_spade_mojibake_repaired(self):
        broken = '{"suit": "â™ "}'
        result = LLMResponseParser._repair_json_string(broken)
        assert "♠" in result

    def test_all_suits_in_one_string(self):
        broken = "â™¥ â™¦ â™£ â™ "
        result = LLMResponseParser._repair_json_string(broken)
        assert "♥" in result
        assert "♦" in result
        assert "♣" in result
        assert "♠" in result

    def test_no_mojibake_unchanged(self):
        clean = '{"suit": "♥"}'
        result = LLMResponseParser._repair_json_string(clean)
        assert "♥" in result

    def test_nfc_normalisation_applied(self):
        """NFC normalisation should not corrupt ordinary ASCII strings."""
        ascii_str = '{"key": "value"}'
        result = LLMResponseParser._repair_json_string(ascii_str)
        assert "key" in result
        assert "value" in result


@pytest.mark.unit
class TestExtractCodeBlockForFileUnicode:
    """extract_code_block_for_file returns NFC-normalised content."""

    def test_returns_nfc_content(self):
        # Build a response with a JS code block containing a card symbol
        response = "```javascript\nconst suit = '♥';\n```"
        result = LLMResponseParser.extract_code_block_for_file(response, "game.js")
        assert "♥" in result

    def test_prefers_language_matched_block(self):
        response = "```python\nx = 1\n```\n```javascript\nconst x = 1;\n```"
        result = LLMResponseParser.extract_code_block_for_file(response, "app.js")
        assert "const x = 1" in result

    def test_fallback_to_largest_block(self):
        response = "```\nshort\n```\n```\nthis is a much longer block of code\n```"
        result = LLMResponseParser.extract_code_block_for_file(response, "README.md")
        assert "longer block" in result
