"""Tests for LLMResponseParser."""
import json

from backend.utils.core.llm_response_parser import LLMResponseParser


class TestLLMResponseParser:
    def test_extract_raw_content_plain_text(self):
        assert (
            LLMResponseParser.extract_raw_content('print("hello")') == 'print("hello")'
        )

    def test_extract_raw_content_strips_markdown(self):
        text = '```python\nprint("hello")\n```'
        assert LLMResponseParser.extract_raw_content(text) == 'print("hello")'

    def test_extract_raw_content_empty(self):
        assert LLMResponseParser.extract_raw_content("") == ""
        assert LLMResponseParser.extract_raw_content("   ") == ""

    def test_extract_single_code_block(self):
        text = "```python\nx = 1\ny = 2\n```"
        assert LLMResponseParser.extract_single_code_block(text) == "x = 1\ny = 2"

    def test_extract_single_code_block_no_lang(self):
        text = "```\nx = 1\n```"
        assert LLMResponseParser.extract_single_code_block(text) == "x = 1"

    def test_extract_single_code_block_unclosed(self):
        text = "```python\nx = 1\ny = 2"
        result = LLMResponseParser.extract_single_code_block(text)
        assert "x = 1" in result

    def test_extract_json_direct(self):
        assert LLMResponseParser.extract_json('{"a": 1}') == {"a": 1}

    def test_extract_json_from_code_block(self):
        text = 'Here is the JSON:\n```json\n{"b": 2}\n```'
        assert LLMResponseParser.extract_json(text) == {"b": 2}

    def test_extract_json_with_surrounding_text(self):
        text = 'Some text before {"c": 3} some text after'
        assert LLMResponseParser.extract_json(text) == {"c": 3}

    def test_extract_json_returns_none_on_failure(self):
        assert LLMResponseParser.extract_json("not json at all") is None

    def test_fix_incomplete_json_missing_braces(self):
        fixed = LLMResponseParser.fix_incomplete_json('{"a": {"b": 1}')
        parsed = json.loads(fixed)
        assert parsed["a"]["b"] == 1

    def test_fix_incomplete_json_missing_brackets(self):
        fixed = LLMResponseParser.fix_incomplete_json('{"a": [1, 2')
        parsed = json.loads(fixed)
        assert parsed["a"] == [1, 2]

    def test_fix_incomplete_json_trailing_comma(self):
        fixed = LLMResponseParser.fix_incomplete_json('{"a": 1, "b": 2, }')
        parsed = json.loads(fixed)
        assert parsed == {"a": 1, "b": 2}

    def test_extract_multiple_files(self):
        response = (
            "# filename: main.py\n"
            "```python\n"
            "print('hello')\n"
            "```\n"
            "\n"
            "# filename: config.json\n"
            "```json\n"
            '{"key": "value"}\n'
            "```"
        )
        files = LLMResponseParser.extract_multiple_files(response)
        assert "main.py" in files
        assert "config.json" in files
        assert "print('hello')" in files["main.py"]
        assert '"key"' in files["config.json"]

    def test_extract_multiple_files_empty(self):
        assert LLMResponseParser.extract_multiple_files("no files here") == {}

    def test_extract_multiple_files_unclosed_block(self):
        response = "# filename: test.py\n" "```python\n" "x = 1\n"
        files = LLMResponseParser.extract_multiple_files(response)
        assert "test.py" in files
