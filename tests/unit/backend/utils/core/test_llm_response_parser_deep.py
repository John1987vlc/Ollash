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
