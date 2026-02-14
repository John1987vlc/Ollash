"""
Unit tests for ErrorKnowledgeBase system.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock

from backend.utils.core.error_knowledge_base import ErrorKnowledgeBase, ErrorPattern


@pytest.fixture
def temp_kb_dir(tmp_path):
    """Create a temporary knowledge base directory."""
    return tmp_path / "knowledge"


@pytest.fixture
def logger_mock():
    """Create a mock logger."""
    return Mock()


@pytest.fixture
def error_kb(temp_kb_dir, logger_mock):
    """Create an ErrorKnowledgeBase instance."""
    return ErrorKnowledgeBase(temp_kb_dir, logger_mock, enable_persistence=True)


class TestErrorPatternClass:
    """Test ErrorPattern dataclass."""
    
    def test_create_error_pattern(self):
        """Test creating an error pattern."""
        pattern = ErrorPattern(
            pattern_id="abc123",
            error_type="syntax",
            affected_file_type=".py",
            description="Missing colon in function definition",
            example_error="def my_func()  # Missing colon",
            prevention_tip="Always use colon after function definition",
            solution_template="Add ':' after function signature",
            language="python"
        )
        
        assert pattern.pattern_id == "abc123"
        assert pattern.error_type == "syntax"
        assert pattern.frequency == 1
        assert pattern.severity == "medium"
    
    def test_pattern_to_dict(self):
        """Test converting pattern to dict."""
        pattern = ErrorPattern(
            pattern_id="test",
            error_type="syntax",
            affected_file_type=".py",
            description="Test",
            example_error="Error",
            prevention_tip="Tip",
            solution_template="Solution",
            language="python"
        )
        
        result = pattern.to_dict()
        assert isinstance(result, dict)
        assert result["pattern_id"] == "test"
        assert result["error_type"] == "syntax"


class TestKnowledgeBaseRecording:
    """Test recording errors."""
    
    def test_record_new_error(self, error_kb):
        """Test recording a new error."""
        pattern_id = error_kb.record_error(
            file_path="main.py",
            error_type="syntax",
            error_message="SyntaxError: invalid syntax",
            file_content="def my_func()  # missing colon",
            context="Python function definition"
        )
        
        assert isinstance(pattern_id, str)
        assert len(pattern_id) > 0
        assert pattern_id in error_kb.patterns
    
    def test_duplicate_error_increases_frequency(self, error_kb):
        """Test that duplicate errors increase frequency counter."""
        pattern_id1 = error_kb.record_error(
            file_path="test.py",
            error_type="import",
            error_message="ImportError: no module named 'foo'",
            file_content="import foo"
        )
        
        pattern_id2 = error_kb.record_error(
            file_path="test2.py",
            error_type="import",
            error_message="ImportError: no module named 'foo'",
            file_content="import foo"
        )
        
        # Should be same pattern due to similar error
        assert pattern_id1 == pattern_id2
        assert error_kb.patterns[pattern_id1].frequency >= 2


class TestKnowledgeBaseQuerying:
    """Test querying the knowledge base."""
    
    def test_query_similar_errors(self, error_kb):
        """Test querying for similar errors."""
        # Record some errors
        error_kb.record_error(
            "model.py",
            "type",
            "TypeError: unsupported operand type",
            "x = 'string' + 5"
        )
        error_kb.record_error(
            "service.py",
            "type",
            "TypeError: unsupported operand type",
            "result = obj1 + obj2"
        )
        
        # Query similar errors
        similar = error_kb.query_similar_errors("new_file.py", "python", "type", max_results=5)
        
        assert len(similar) > 0
        assert all(p.error_type == "type" for p in similar)
    
    def test_query_by_language_filter(self, error_kb):
        """Test that language filtering works."""
        error_kb.record_error("py_file.py", "syntax", "Error", "code")
        error_kb.record_error("js_file.js", "logic", "Error", "code")
        
        python_errors = error_kb.query_similar_errors(
            "test.py", "python", max_results=10
        )
        
        # Should only return Python errors
        assert all(p.language == "python" for p in python_errors)


class TestPreventionWarnings:
    """Test prevention warning generation."""
    
    def test_get_prevention_warnings(self, error_kb):
        """Test generating prevention warnings."""
        # Record some errors
        for i in range(3):
            error_kb.record_error(
                f"file{i}.py",
                "import",
                f"ImportError: No module named 'pkg{i}'",
                "import nonexistent"
            )
        
        warnings = error_kb.get_prevention_warnings(
            "new_file.py", "MyProject", "python"
        )
        
        if warnings:  # May be empty if no matching errors
            assert "careful" in warnings.lower() or "avoid" in warnings.lower()


class TestLanguageDetection:
    """Test language detection."""
    
    def test_detect_language_python(self, error_kb):
        """Test detecting Python files."""
        lang = error_kb._detect_language("models/user.py")
        assert lang == "python"
    
    def test_detect_language_javascript(self, error_kb):
        """Test detecting JavaScript files."""
        lang = error_kb._detect_language("src/app.js")
        assert lang == "javascript"
    
    def test_detect_language_unknown(self, error_kb):
        """Test unknown language handling."""
        lang = error_kb._detect_language("file.unknown")
        assert lang == "unknown"


class TestStatistics:
    """Test knowledge base statistics."""
    
    def test_empty_statistics(self, error_kb):
        """Test stats on empty KB."""
        stats = error_kb.get_error_statistics()
        # Verify stats returns a dictionary
        assert isinstance(stats, dict)
    
    def test_populated_statistics(self, error_kb):
        """Test stats on populated KB."""
        error_kb.record_error("file.py", "syntax", "Error", "code")
        error_kb.record_error("file.js", "logic", "Error", "code")
        
        stats = error_kb.get_error_statistics()
        # Verify stats contains pattern count information
        assert isinstance(stats, dict) and len(stats) > 0
        assert "by_type" in stats
        assert "by_language" in stats
    
    def test_statistics_by_type(self, error_kb):
        """Test statistics grouped by error type."""
        error_kb.record_error("f1.py", "syntax", "Error1", "code")
        error_kb.record_error("f2.py", "syntax", "Error2", "code")
        error_kb.record_error("f3.py", "logic", "Error3", "code")
        
        stats = error_kb.get_error_statistics()
        assert "syntax" in stats["by_type"]
        assert "logic" in stats["by_type"]


class TestKnowledgeBasePersistence:
    """Test persistence to disk."""
    
    def test_save_and_load(self, temp_kb_dir, logger_mock):
        """Test saving and loading KB."""
        kb1 = ErrorKnowledgeBase(temp_kb_dir, logger_mock, enable_persistence=True)
        kb1.record_error("test.py", "syntax", "SyntaxError", "code")
        
        # Create new instance (should load from disk)
        kb2 = ErrorKnowledgeBase(temp_kb_dir, logger_mock, enable_persistence=True)
        
        assert len(kb2.patterns) > 0
    
    def test_export_knowledge(self, error_kb, tmp_path):
        """Test exporting knowledge base."""
        error_kb.record_error("test.py", "syntax", "Error", "code")
        
        export_file = tmp_path / "exported_knowledge.json"
        error_kb.export_knowledge(export_file)
        
        assert export_file.exists()
        
        with open(export_file) as f:
            data = json.load(f)
            assert "patterns" in data
            assert len(data["patterns"]) > 0
