"""Unit tests for EnhancedFileContentGenerator."""

import pytest
from unittest.mock import MagicMock, patch

from backend.utils.domains.auto_generation.enhanced_file_content_generator import (
    EnhancedFileContentGenerator,
)


@pytest.fixture
def mock_llm():
    client = MagicMock()
    client.chat.return_value = (
        {"message": {"content": "def calculate():\n    return 42\n" + "#" * 60}},
        {"prompt_tokens": 10, "completion_tokens": 20},
    )
    return client


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def mock_response_parser():
    parser = MagicMock()
    parser.extract_code_block.return_value = None  # passthrough by default
    return parser


@pytest.fixture
def mock_code_patcher():
    patcher = MagicMock()
    patcher.edit_existing_file.return_value = "patched content"
    return patcher


@pytest.fixture
def generator(mock_llm, mock_logger, mock_response_parser, mock_code_patcher):
    return EnhancedFileContentGenerator(
        llm_client=mock_llm,
        logger=mock_logger,
        response_parser=mock_response_parser,
        code_patcher=mock_code_patcher,
    )


@pytest.mark.unit
class TestValidateContent:
    """Tests for _validate_content — verifies no duplicates exist."""

    def test_validate_content_missing_export(self, generator):
        content = "def wrong_name():\n    return 42\n" + "#" * 60
        assert generator._validate_content(content, "calc.py", ["calculate"], []) is False

    def test_validate_content_passes_with_correct_export(self, generator):
        content = "def calculate():\n    return 42\n" + "#" * 60
        assert generator._validate_content(content, "calc.py", ["calculate"], []) is True

    def test_validate_content_detects_todo_placeholder(self, generator):
        content = "def calculate():\n    # TODO: implement\n    pass\n" + "#" * 60
        assert generator._validate_content(content, "calc.py", ["calculate"], []) is False

    def test_validate_content_detects_fixme_placeholder(self, generator):
        content = "def calculate():\n    # FIXME: broken\n    return 0\n" + "#" * 60
        assert generator._validate_content(content, "calc.py", ["calculate"], []) is False

    def test_validate_content_skeleton_detection_pass_and_ellipsis(self, generator):
        # Single export but content has multiple passes and is short
        skeleton = "def calculate():\n    pass\ndef other():\n    pass\ndef third():\n    ..."
        assert generator._validate_content(skeleton, "calc.py", ["calculate"], []) is False

    def test_validate_content_too_short(self, generator):
        assert generator._validate_content("x = 1", "calc.py", [], []) is False

    def test_validate_content_unmatched_parentheses(self, generator):
        content = "def calculate(:\n    return 42\n" + "#" * 60
        assert generator._validate_content(content, "calc.py", ["calculate"], []) is False

    def test_only_one_validate_content_method_exists(self):
        """Regression: ensure the merge artifact (duplicate) has been removed."""
        import inspect
        import backend.utils.domains.auto_generation.enhanced_file_content_generator as mod
        source = inspect.getsource(mod)
        assert source.count("def _validate_content") == 1, (
            "Duplicate _validate_content found — merge artifact not removed"
        )

    def test_only_one_fallback_skeleton_method_exists(self):
        """Regression: ensure the duplicate _generate_fallback_skeleton has been removed."""
        import inspect
        import backend.utils.domains.auto_generation.enhanced_file_content_generator as mod
        source = inspect.getsource(mod)
        assert source.count("def _generate_fallback_skeleton") == 1, (
            "Duplicate _generate_fallback_skeleton found — merge artifact not removed"
        )

    def test_import_re_at_module_level_not_inside_loop(self):
        """Regression: import re must be at module level, not inside a loop."""
        import inspect
        import backend.utils.domains.auto_generation.enhanced_file_content_generator as mod
        source = inspect.getsource(mod)
        # The top-level import should appear before class definition
        class_pos = source.index("class EnhancedFileContentGenerator")
        import_re_pos = source.index("import re")
        assert import_re_pos < class_pos, "import re must be at module level"


@pytest.mark.unit
class TestGenerateFallbackSkeleton:
    def test_python_skeleton_contains_export(self, generator):
        result = generator._generate_fallback_skeleton("mod.py", "A test module", ["MyClass"], [])
        assert "class MyClass" in result

    def test_python_skeleton_with_function(self, generator):
        result = generator._generate_fallback_skeleton("utils.py", "Utilities", ["helper()"], [])
        assert "def helper" in result

    def test_html_skeleton_structure(self, generator):
        result = generator._generate_fallback_skeleton("index.html", "Landing page", [], [])
        assert "<!DOCTYPE html>" in result

    def test_css_skeleton_structure(self, generator):
        result = generator._generate_fallback_skeleton("style.css", "Styles", [], [])
        assert "/*" in result


@pytest.mark.unit
class TestGenerateFileWithPlan:
    def test_generate_file_success(self, generator, mock_llm, mock_response_parser):
        mock_response_parser.extract_code_block.return_value = "def calculate():\n    return 42\n" + "#" * 60
        logic_plan = {
            "purpose": "Math utilities",
            "exports": ["calculate"],
            "imports": [],
            "main_logic": ["implement calculate"],
            "validation": [],
            "dependencies": [],
        }
        result = generator.generate_file_with_plan(
            "calc.py", logic_plan, "A project", "# README", {}, {}
        )
        assert "calculate" in result

    def test_generate_file_falls_back_to_skeleton_after_all_retries(
        self, mock_llm, mock_logger, mock_response_parser, mock_code_patcher
    ):
        # LLM returns content that always fails validation (too short)
        mock_llm.chat.return_value = (
            {"message": {"content": "x"}},
            {},
        )
        mock_response_parser.extract_code_block.return_value = None
        gen = EnhancedFileContentGenerator(
            llm_client=mock_llm,
            logger=mock_logger,
            response_parser=mock_response_parser,
            code_patcher=mock_code_patcher,
        )
        logic_plan = {
            "purpose": "Fail test",
            "exports": ["MyClass"],
            "imports": [],
            "main_logic": [],
            "validation": [],
            "dependencies": [],
        }
        result = gen.generate_file_with_plan(
            "broken.py", logic_plan, "desc", "# README", {}, {}
        )
        # Should have returned the fallback skeleton
        assert "MyClass" in result
        assert mock_llm.chat.call_count == gen.max_retries


@pytest.mark.unit
class TestRAGIntegration:
    def test_rag_snippets_injected_when_doc_manager_present(
        self, mock_llm, mock_logger, mock_response_parser, mock_code_patcher
    ):
        mock_doc_manager = MagicMock()
        mock_doc_manager.query_documentation.return_value = [
            {"document": "def example(): pass", "source": "docs/api.md", "distance": 0.1}
        ]
        mock_response_parser.extract_code_block.return_value = (
            "def calculate():\n    return 42\n" + "#" * 60
        )

        gen = EnhancedFileContentGenerator(
            llm_client=mock_llm,
            logger=mock_logger,
            response_parser=mock_response_parser,
            documentation_manager=mock_doc_manager,
            code_patcher=mock_code_patcher,
        )

        logic_plan = {
            "purpose": "Math utilities",
            "exports": ["calculate"],
            "imports": [],
            "main_logic": [],
            "validation": [],
            "dependencies": [],
        }
        gen.generate_file_with_plan("calc.py", logic_plan, "A project", "# README", {}, {})

        mock_doc_manager.query_documentation.assert_called_once()

    def test_no_rag_when_doc_manager_absent(self, generator, mock_llm):
        # generator fixture has no documentation_manager
        assert generator.documentation_manager is None
        logic_plan = {
            "purpose": "Test",
            "exports": ["calculate"],
            "imports": [],
            "main_logic": [],
            "validation": [],
            "dependencies": [],
        }
        mock_llm.chat.return_value = (
            {"message": {"content": "def calculate():\n    return 42\n" + "#" * 60}},
            {},
        )
        # Should not raise even without a documentation_manager
        result = generator.generate_file_with_plan("calc.py", logic_plan, "desc", "# README", {}, {})
        assert result is not None


@pytest.mark.unit
class TestEditExistingFileDelegates:
    def test_edit_delegates_to_code_patcher(self, generator, mock_code_patcher):
        generator.edit_existing_file("file.py", "original", "# README", [], "partial")
        mock_code_patcher.edit_existing_file.assert_called_once_with(
            "file.py", "original", "# README", [], "partial"
        )
