"""Unit tests for signature_extractor.py (extracted from phase_context.py)."""

import pytest

from backend.utils.domains.auto_generation.utilities.signature_extractor import (
    extract_signatures,
    extract_signatures_regex,
)


class TestExtractSignaturesRegex:
    @pytest.mark.unit
    def test_extracts_typescript_function(self):
        code = "export async function fetchData(url: string): Promise<Response> {"
        result = extract_signatures_regex(code, ".ts")
        assert any("fetchData" in line for line in result)

    @pytest.mark.unit
    def test_extracts_typescript_class(self):
        code = "export abstract class UserService implements IUserService {"
        result = extract_signatures_regex(code, ".ts")
        assert any("UserService" in line for line in result)

    @pytest.mark.unit
    def test_extracts_javascript_arrow_function(self):
        code = "const handleClick = async (event) => {"
        result = extract_signatures_regex(code, ".js")
        assert any("handleClick" in line for line in result)

    @pytest.mark.unit
    def test_extracts_go_function(self):
        code = "func (s *Server) HandleRequest(w http.ResponseWriter, r *http.Request) {"
        result = extract_signatures_regex(code, ".go")
        assert any("HandleRequest" in line for line in result)

    @pytest.mark.unit
    def test_extracts_go_struct(self):
        code = "type User struct {"
        result = extract_signatures_regex(code, ".go")
        assert any("User" in line for line in result)

    @pytest.mark.unit
    def test_extracts_rust_pub_fn(self):
        code = "pub async fn process_request(req: Request) -> Response {"
        result = extract_signatures_regex(code, ".rs")
        assert any("process_request" in line for line in result)

    @pytest.mark.unit
    def test_returns_empty_list_for_no_matches(self):
        code = "let x = 1;"
        result = extract_signatures_regex(code, ".js")
        assert result == []

    @pytest.mark.unit
    def test_fallback_pattern_for_unknown_extension(self):
        code = "function myFunc() { return 1; }"
        result = extract_signatures_regex(code, ".unknown")
        assert any("myFunc" in line for line in result)

    @pytest.mark.unit
    def test_returns_list_type(self):
        result = extract_signatures_regex("", ".py")
        assert isinstance(result, list)


class TestExtractSignatures:
    @pytest.mark.unit
    def test_python_function_signature(self):
        code = "def greet(name: str) -> str:\n    return f'Hello {name}'"
        result = extract_signatures(code, "module/greet.py")
        assert "def greet(" in result
        assert "name: str" in result

    @pytest.mark.unit
    def test_python_async_function(self):
        code = "async def fetch(url: str) -> bytes:\n    pass"
        result = extract_signatures(code, "fetcher.py")
        assert "async def fetch(" in result

    @pytest.mark.unit
    def test_python_class_with_bases(self):
        code = "class Animal(Base):\n    pass"
        result = extract_signatures(code, "models.py")
        assert "class Animal(Base)" in result

    @pytest.mark.unit
    def test_python_syntax_error_falls_back_to_regex(self):
        code = "def broken("  # invalid Python
        result = extract_signatures(code, "broken.py")
        # Regex fallback should return something or content[:500]
        assert isinstance(result, str)

    @pytest.mark.unit
    def test_non_python_uses_regex(self):
        code = "export function hello(): void {"
        result = extract_signatures(code, "index.ts")
        assert "hello" in result

    @pytest.mark.unit
    def test_returns_content_slice_when_no_signatures(self):
        code = "const x = 42;"
        result = extract_signatures(code, "config.js")
        # Should return content[:500] as fallback
        assert result == code[:500]

    @pytest.mark.unit
    def test_empty_file_returns_empty_string(self):
        result = extract_signatures("", "empty.py")
        assert result == ""

    @pytest.mark.unit
    def test_multiple_functions_all_extracted(self):
        code = "def foo():\n    pass\n\ndef bar() -> int:\n    return 1"
        result = extract_signatures(code, "utils.py")
        assert "foo" in result
        assert "bar" in result

    @pytest.mark.unit
    def test_return_type_is_string(self):
        result = extract_signatures("x = 1", "misc.py")
        assert isinstance(result, str)
