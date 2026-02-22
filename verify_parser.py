from backend.utils.core.llm.llm_response_parser import LLMResponseParser

def test_think_removal():
    response = """<think>
    I should write a python function that adds two numbers.
    </think>
    ```python
    def add(a, b):
        return a + b
    ```"""
    
    cleaned, think = LLMResponseParser.remove_think_blocks(response)
    print("Cleaned:")
    print(cleaned)
    print("Think:")
    print(think)
    
    code = LLMResponseParser.extract_single_code_block(response)
    print("Extracted Code:")
    print(code)
    assert "def add" in code
    assert "<think>" not in code

def test_unclosed_think():
    response = """<think>
    I am thinking and I will never close this tag because I reached num_predict limit.
    def this_is_draft():
        pass
    """
    cleaned, think = LLMResponseParser.remove_think_blocks(response)
    print("Cleaned (Unclosed):")
    print(cleaned)
    print("Think (Unclosed):")
    print(think)
    assert cleaned == ""
    assert "draft" in think

def test_json_with_think():
    response = """<think>
    Planning the structure.
    </think>
    {
        "project": "checkers",
        "files": ["index.html"]
    }"""
    data = LLMResponseParser.extract_json(response)
    print("Extracted JSON:", data)
    assert data["project"] == "checkers"

if __name__ == "__main__":
    test_think_removal()
    test_unclosed_think()
    test_json_with_think()
    print("\nAll parser tests passed!")
