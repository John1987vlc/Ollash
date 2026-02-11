"""Tests for core utilities: LLMResponseParser, FileValidator, Heartbeat."""
import json

from src.utils.core.llm_response_parser import LLMResponseParser
from src.utils.core.file_validator import FileValidator, ValidationStatus
from src.utils.core.heartbeat import Heartbeat


class TestLLMResponseParser:

    def test_extract_raw_content_plain_text(self):
        assert LLMResponseParser.extract_raw_content('print("hello")') == 'print("hello")'

    def test_extract_raw_content_strips_markdown(self):
        text = '```python\nprint("hello")\n```'
        assert LLMResponseParser.extract_raw_content(text) == 'print("hello")'

    def test_extract_raw_content_empty(self):
        assert LLMResponseParser.extract_raw_content("") == ""
        assert LLMResponseParser.extract_raw_content("   ") == ""

    def test_extract_single_code_block(self):
        text = '```python\nx = 1\ny = 2\n```'
        assert LLMResponseParser.extract_single_code_block(text) == "x = 1\ny = 2"

    def test_extract_single_code_block_no_lang(self):
        text = '```\nx = 1\n```'
        assert LLMResponseParser.extract_single_code_block(text) == "x = 1"

    def test_extract_single_code_block_unclosed(self):
        text = '```python\nx = 1\ny = 2'
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
            '```json\n'
            '{"key": "value"}\n'
            '```'
        )
        files = LLMResponseParser.extract_multiple_files(response)
        assert "main.py" in files
        assert "config.json" in files
        assert "print('hello')" in files["main.py"]
        assert '"key"' in files["config.json"]

    def test_extract_multiple_files_empty(self):
        assert LLMResponseParser.extract_multiple_files("no files here") == {}

    def test_extract_multiple_files_unclosed_block(self):
        response = (
            "# filename: test.py\n"
            "```python\n"
            "x = 1\n"
        )
        files = LLMResponseParser.extract_multiple_files(response)
        assert "test.py" in files


class TestFileValidator:

    def setup_method(self):
        self.v = FileValidator()

    def test_valid_python(self):
        code = "def hello():\n    return True\n\nprint(hello())"
        r = self.v.validate("test.py", code)
        assert r.status == ValidationStatus.VALID

    def test_invalid_python_syntax(self):
        code = "def hello(\n    return True\n    pass"
        r = self.v.validate("bad.py", code)
        assert r.status == ValidationStatus.SYNTAX_ERROR

    def test_valid_json(self):
        r = self.v.validate("config.json", '{"key": "value"}')
        assert r.status == ValidationStatus.VALID

    def test_invalid_json(self):
        r = self.v.validate("bad.json", '{"key": }')
        assert r.status == ValidationStatus.SYNTAX_ERROR

    def test_empty_file(self):
        r = self.v.validate("empty.py", "")
        assert r.status == ValidationStatus.EMPTY

    def test_whitespace_only_file(self):
        r = self.v.validate("ws.py", "   \n  \n  ")
        assert r.status == ValidationStatus.EMPTY

    def test_truncated_python(self):
        r = self.v.validate("short.py", "x = 1")
        assert r.status == ValidationStatus.TRUNCATED

    def test_valid_html(self):
        html = "<!DOCTYPE html>\n<html>\n<head></head>\n<body>\n<p>Hi</p>\n</body>\n</html>"
        r = self.v.validate("page.html", html)
        assert r.status == ValidationStatus.VALID

    def test_truncated_html(self):
        r = self.v.validate("bad.html", "<div>hi</div>")
        assert r.status == ValidationStatus.TRUNCATED

    def test_brace_language_truncated(self):
        code = "function test() {\n  if (true) {\n    console.log('hi')"
        r = self.v.validate("app.js", code)
        assert r.status == ValidationStatus.TRUNCATED

    def test_brace_language_valid(self):
        code = "function test() {\n  if (true) {\n    console.log('hi')\n  }\n}"
        r = self.v.validate("app.js", code)
        assert r.status == ValidationStatus.VALID

    def test_unknown_extension(self):
        r = self.v.validate("data.csv", "a,b,c\n1,2,3")
        assert r.status == ValidationStatus.VALID

    def test_batch_validation(self):
        files = {
            "a.py": "x = 1\ny = 2\nz = 3",
            "b.json": '{"k": 1}',
            "c.txt": "hello",
        }
        results = self.v.validate_batch(files)
        assert len(results) == 3

    def test_validation_result_fields(self):
        r = self.v.validate("test.py", "x = 1\ny = 2\nz = 3")
        assert r.file_path == "test.py"
        assert r.line_count == 3
        assert r.char_count > 0
        assert isinstance(r.message, str)


class TestHeartbeat:

    def test_heartbeat_start_stop(self):
        hb = Heartbeat("test-model", "test-task", interval=60)
        hb.start()
        hb.stop()
        # No assertion needed - just verify no crash

    def test_heartbeat_with_logger(self):
        class FakeLogger:
            def __init__(self):
                self.messages = []
            def info(self, msg):
                self.messages.append(msg)

        logger = FakeLogger()
        hb = Heartbeat("model", "task", interval=60, logger=logger)
        hb.start()
        hb.stop()
        # Logger should not have been called since interval > test duration
