import pytest

from backend.utils.core.llm.llm_response_parser import LLMResponseParser


def test_remove_think_blocks():
    text = "<think>deep reasoning</think>actual response"
    cleaned, thought = LLMResponseParser.remove_think_blocks(text)
    assert cleaned == "actual response"
    assert thought == "deep reasoning"

    text_proc = "<thinking_process>step by step</thinking_process>Done."
    cleaned, thought = LLMResponseParser.remove_think_blocks(text_proc)
    assert cleaned == "Done."
    assert thought == "step by step"


def test_extract_json_with_comments_and_trailing_commas():
    # Test step 5 heuristic: rescue JSON with JS comments and trailing commas
    text = """
    Here is the config:
    {
        "name": "ollash", // name of the project
        "version": "1.0",
        "features": ["auto", "chat",],
    }
    Hope it works!
    """
    result = LLMResponseParser.extract_json(text)
    assert result == {"name": "ollash", "version": "1.0", "features": ["auto", "chat"]}


def test_extract_json_from_tags():
    text = '<plan_json>{"task": "build"}</plan_json>'
    assert LLMResponseParser.extract_json(text) == {"task": "build"}

    text_md = '<backlog_json>\n```json\n[{"id": 1}]\n```\n</backlog_json>'
    assert LLMResponseParser.extract_json(text_md) == [{"id": 1}]


def test_extract_multiple_files_variations():
    response = """
    // filename: src/main.py
    ```python
    print(1)
    ```
    # filename: README.md
    ```markdown
    # Hello
    ```
    """
    files = LLMResponseParser.extract_multiple_files(response)
    assert files["src/main.py"] == "print(1)"
    assert files["README.md"] == "# Hello"


def test_extract_multiple_files_no_filename_in_block():
    # Filename outside the block
    response = """
    File: config.json
    // filename: config.json
    ```
    {"a": 1}
    ```
    """
    files = LLMResponseParser.extract_multiple_files(response)
    assert files["config.json"] == '{"a": 1}'


# ---------------------------------------------------------------------------
# Tests: extract_code_block_for_file()
# ---------------------------------------------------------------------------


class TestExtractCodeBlockForFile:
    @pytest.mark.unit
    def test_selects_javascript_block_for_js_file(self):
        response = (
            "Here is the explanation:\n"
            "```python\nprint('hello')\n```\n\n"
            "And here is the JS implementation:\n"
            "```javascript\nconsole.log('hello');\n```"
        )
        result = LLMResponseParser.extract_code_block_for_file(response, "src/app.js")
        assert "console.log" in result
        assert "print(" not in result

    @pytest.mark.unit
    def test_selects_html_block_for_html_file(self):
        response = "Example JSON:\n```json\n{}\n```\n\nThe HTML:\n```html\n<!DOCTYPE html>\n<html></html>\n```"
        result = LLMResponseParser.extract_code_block_for_file(response, "index.html")
        assert "DOCTYPE" in result

    @pytest.mark.unit
    def test_selects_python_block_for_py_file(self):
        response = "Usage example:\n```bash\npython main.py\n```\n\nImplementation:\n```python\ndef main(): pass\n```"
        result = LLMResponseParser.extract_code_block_for_file(response, "src/main.py")
        assert "def main" in result
        assert "python main.py" not in result

    @pytest.mark.unit
    def test_selects_css_block_for_css_file(self):
        response = "```html\n<div class='box'></div>\n```\n```css\n.box { color: red; }\n```"
        result = LLMResponseParser.extract_code_block_for_file(response, "styles.css")
        assert ".box" in result
        assert "<div" not in result

    @pytest.mark.unit
    def test_fallback_largest_block_when_no_hint_match(self):
        """No language hint matches .js → take the largest block."""
        response = "```bash\ncd /tmp\n```\n\n```\nconst x = 1;\nconst y = 2;\nfunction add(a, b) { return a + b; }\n```"
        result = LLMResponseParser.extract_code_block_for_file(response, "utils.js")
        assert "function add" in result

    @pytest.mark.unit
    def test_single_block_always_returned_regardless_of_ext(self):
        response = "```python\ndef foo(): pass\n```"
        result = LLMResponseParser.extract_code_block_for_file(response, "anything.rb")
        assert "def foo" in result

    @pytest.mark.unit
    def test_empty_response_returns_empty_string(self):
        assert LLMResponseParser.extract_code_block_for_file("", "app.py") == ""

    @pytest.mark.unit
    def test_think_blocks_stripped_before_selection(self):
        response = "<think>I should write JS code here</think>\n```javascript\nconst x = 1;\n```"
        result = LLMResponseParser.extract_code_block_for_file(response, "app.js")
        assert "const x" in result
        assert "think" not in result.lower()

    @pytest.mark.unit
    def test_no_blocks_falls_back_to_extract_single(self):
        """When there are no fenced blocks, behaves like extract_single_code_block."""
        response = "const x = 1;\nconst y = 2;"
        result = LLMResponseParser.extract_code_block_for_file(response, "app.js")
        # Falls back to extract_single_code_block which returns the raw text
        assert "const x" in result

    @pytest.mark.unit
    def test_typescript_hints_match_ts_file(self):
        response = "```javascript\nvar x = 1;\n```\n```typescript\nconst x: number = 1;\n```"
        result = LLMResponseParser.extract_code_block_for_file(response, "app.ts")
        assert "number" in result


# ----------------------------------------------------------------
# Fix 1 — C# and other new lang_map entries + word-boundary anchor
# ----------------------------------------------------------------


@pytest.mark.unit
class TestExtractCodeBlockForFileCsharp:
    def test_csharp_block_not_prefixed_with_harp(self):
        """Regression: ```csharp must NOT produce 'harp...' as the first word."""
        response = "```csharp\nnamespace App;\npublic class Foo {}\n```"
        result = LLMResponseParser.extract_code_block_for_file(response, "Foo.cs")
        assert not result.startswith("harp"), repr(result[:40])
        assert "namespace" in result

    def test_csharp_canonical_alias_wins(self):
        """'csharp' alias is tried before 'cs'; both must work."""
        response = "```csharp\nusing System;\n```"
        result = LLMResponseParser.extract_code_block_for_file(response, "Program.cs")
        assert "using System" in result

    def test_cs_short_alias_also_matches(self):
        response = "```cs\nusing System;\n```"
        result = LLMResponseParser.extract_code_block_for_file(response, "Program.cs")
        assert "using System" in result

    def test_cs_alias_does_not_match_csharp_fence(self):
        """The 'cs' pattern must NOT produce 'harp' when the fence says 'csharp'."""
        response = "```csharp\nvar x = 1;\n```"
        result = LLMResponseParser.extract_code_block_for_file(response, "Test.cs")
        assert result == "var x = 1;"

    def test_kotlin_block_selected_for_kt_file(self):
        response = "```kotlin\nfun main() {}\n```"
        result = LLMResponseParser.extract_code_block_for_file(response, "Main.kt")
        assert "fun main" in result

    def test_cpp_block_not_confused_with_c_block(self):
        """Two blocks: ```c and ```cpp — a .cpp file must pick the cpp block."""
        response = "```c\nint main() { return 0; }\n```\n```cpp\n#include<iostream>\n```"
        result = LLMResponseParser.extract_code_block_for_file(response, "main.cpp")
        assert "iostream" in result

    def test_ruby_block_selected_for_rb_file(self):
        response = "```ruby\nclass Dog\nend\n```"
        result = LLMResponseParser.extract_code_block_for_file(response, "dog.rb")
        assert "class Dog" in result

    def test_dart_block_selected_for_dart_file(self):
        response = "```dart\nvoid main() {}\n```"
        result = LLMResponseParser.extract_code_block_for_file(response, "main.dart")
        assert "void main" in result
