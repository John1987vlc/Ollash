"""Tests for FileValidator."""
from backend.utils.core.file_validator import FileValidator, ValidationStatus


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
