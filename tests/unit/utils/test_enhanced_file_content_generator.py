"""Tests for EnhancedFileContentGenerator."""

import json
from unittest.mock import MagicMock
import pytest
from backend.utils.domains.auto_generation.enhanced_file_content_generator import EnhancedFileContentGenerator


@pytest.fixture
def mock_llm_client():
    client = MagicMock()
    
    def mock_chat(messages, **kwargs):
        # Return a simple code string without markdown backticks 
        # to ensure it doesn't get messed up by parser
        content = """
import os

def main():
    \"\"\"This is a valid implementation with more than twenty characters.\"\"\"
    value_a = 100
    value_b = 200
    result = value_a + value_b
    print(f"The result is {result}")
    return result
"""
        response = {
            "message": {
                "content": content
            }
        }
        stats = {"total_tokens": 100}
        return response, stats

    client.chat.side_effect = mock_chat
    return client


@pytest.fixture
def generator(mock_llm_client):
    logger = MagicMock()
    # We mock response_parser.extract_code_block to just return the content as is
    generator_obj = EnhancedFileContentGenerator(llm_client=mock_llm_client, logger=logger)
    generator_obj.response_parser = MagicMock()
    generator_obj.response_parser.extract_code_block.side_effect = lambda x: x
    return generator_obj


class TestEnhancedFileContentGenerator:
    def test_generate_file_with_plan_success(self, generator):
        plan = {
            "purpose": "Test script",
            "exports": ["main()"],
            "imports": ["os"],
            "main_logic": ["Do math"],
            "validation": ["Check result"]
        }
        
        content = generator.generate_file_with_plan(
            "test.py", plan, "desc", "# Readme", {}, {}
        )
        
        # Verify it didn't fall back to skeleton
        # The skeleton would contain "pass" or "TODO"
        assert "def main():" in content
        assert "print(f\"The result is" in content
        assert generator.llm_client.chat.called

    def test_validate_content_positive(self, generator):
        content = """
def main():
    \"\"\"Enough characters here to pass the 20 char limit.\"\"\"
    x = 10
    y = 20
    return x + y
"""
        exports = ["main()"]
        assert generator._validate_content(content, "test.py", exports, []) is True

    def test_validate_content_negative_short(self, generator):
        content = "too short"
        assert generator._validate_content(content, "test.py", ["main"], []) is False

    def test_validate_content_negative_missing_export(self, generator):
        content = """
def other_stuff():
    \"\"\"Does not have the required word.\"\"\"
    a = 1
    b = 2
    return a + b
"""
        assert generator._validate_content(content, "test.py", ["main"], []) is False

    def test_validate_content_negative_placeholders(self, generator):
        content = """
def main():
    \"\"\"Has the word but also a placeholder.\"\"\"
    # TODO: implement
    pass
"""
        assert generator._validate_content(content, "test.py", ["main"], []) is False

    def test_generate_fallback_skeleton_python(self, generator):
        skeleton = generator._generate_fallback_skeleton(
            "app.py", "App core", ["run()", "Config"], ["os"]
        )
        assert "def run():" in skeleton
        assert "class Config:" in skeleton
        assert "App core" in skeleton
