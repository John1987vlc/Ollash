"""Unit tests for AutomaticLearningSystem module."""

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.utils.core.automatic_learning import (AutomaticLearningSystem,
                                                   CorrectionPattern,
                                                   LearningIndexer,
                                                   PostMortemAnalyzer)


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return MagicMock()


@pytest.fixture
def tmp_project(tmp_path):
    """Create temporary project structure."""
    ollash_dir = tmp_path / ".ollash"
    ollash_dir.mkdir()
    return tmp_path


class TestCorrectionPattern:
    """Test CorrectionPattern data class."""

    def test_create_pattern(self):
        """Test creating a correction pattern."""
        pattern = CorrectionPattern(
            error_signature="abc123",
            error_message="SyntaxError: invalid syntax",
            error_type="SyntaxError",
            file_path="main.py",
            language="python",
            initial_code="def func( x:",
            corrected_code="def func(x):",
            correction_steps=["Removed space", "Added closing paren"],
            success_metrics={"syntax_valid": True},
            timestamp="2026-02-11T10:00:00",
            project_name="test_project",
            phase="senior_review",
        )

        assert pattern.error_type == "SyntaxError"
        assert pattern.language == "python"
        assert len(pattern.correction_steps) == 2

    def test_pattern_attributes(self):
        """Test that all pattern attributes are accessible."""
        pattern = CorrectionPattern(
            error_signature="sig",
            error_message="msg",
            error_type="type",
            file_path="path",
            language="lang",
            initial_code="init",
            corrected_code="corrected",
            correction_steps=["step1"],
            success_metrics={"metric": 0.9},
            timestamp="2026-02-11",
            project_name="proj",
            phase="phase1",
        )

        assert pattern.error_signature == "sig"
        assert pattern.success_metrics["metric"] == 0.9


class TestPostMortemAnalyzer:
    """Test PostMortemAnalyzer."""

    def test_analyzer_initialization(self, mock_logger, tmp_project):
        """Test analyzer initialization."""
        analyzer = PostMortemAnalyzer(
            logger=mock_logger,
            project_root=tmp_project,
        )

        assert analyzer.project_root == tmp_project
        assert analyzer.postmortem_dir.exists()

    def test_analyze_correction(self, mock_logger, tmp_project):
        """Test creating a correction pattern."""
        analyzer = PostMortemAnalyzer(
            logger=mock_logger,
            project_root=tmp_project,
        )

        pattern = analyzer.analyze_correction(
            error_message="SyntaxError: invalid syntax",
            error_type="SyntaxError",
            file_path="main.py",
            language="python",
            initial_code="def func( x:",
            corrected_code="def func(x):",
            correction_steps=["Fixed spacing"],
            success_metrics={"syntax_valid": True},
            phase="senior_review",
            project_name="test_proj",
        )

        assert pattern.error_type == "SyntaxError"
        assert len(pattern.error_signature) > 0

    def test_save_pattern(self, mock_logger, tmp_project):
        """Test saving a correction pattern."""
        analyzer = PostMortemAnalyzer(
            logger=mock_logger,
            project_root=tmp_project,
        )

        pattern = analyzer.analyze_correction(
            error_message="IndentationError",
            error_type="IndentationError",
            file_path="utils.py",
            language="python",
            initial_code="  def func():",
            corrected_code="def func():",
            correction_steps=["Fixed indent"],
            success_metrics={"syntax_valid": True},
            phase="generation",
            project_name="test",
        )

        file_path = analyzer.save_pattern(pattern)

        assert file_path.exists()

        # Verify saved content
        with open(file_path) as f:
            saved = json.load(f)

        assert saved["error_type"] == "IndentationError"
        assert saved["language"] == "python"

    def test_pattern_directory_created(self, mock_logger, tmp_project):
        """Test that postmortem directory is created."""
        analyzer = PostMortemAnalyzer(
            logger=mock_logger,
            project_root=tmp_project,
        )

        assert analyzer.postmortem_dir.exists()
        assert analyzer.postmortem_dir.is_dir()


class TestLearningIndexer:
    """Test LearningIndexer."""

    def test_indexer_initialization(self, mock_logger, tmp_project):
        """Test indexer initialization."""
        indexer = LearningIndexer(
            logger=mock_logger,
            project_root=tmp_project,
        )

        assert indexer.project_root == tmp_project

    def test_index_pattern(self, mock_logger, tmp_project):
        """Test indexing a correction pattern."""
        indexer = LearningIndexer(
            logger=mock_logger,
            project_root=tmp_project,
        )

        pattern = CorrectionPattern(
            error_signature="test_sig",
            error_message="Test error",
            error_type="TestError",
            file_path="test.py",
            language="python",
            initial_code="bad code",
            corrected_code="good code",
            correction_steps=["Fix"],
            success_metrics={},
            timestamp="2026-02-11",
            project_name="test",
            phase="test",
        )

        # Should not raise error
        indexer.index_pattern(pattern)

    def test_find_similar_patterns(self, mock_logger, tmp_project):
        """Test finding similar patterns."""
        indexer = LearningIndexer(
            logger=mock_logger,
            project_root=tmp_project,
        )

        # Should return empty list if no patterns indexed
        similar = indexer.find_similar_patterns(
            error_message="Some error",
            language="python",
            limit=3,
        )

        assert isinstance(similar, list)

    def test_chromadb_unavailable(self, mock_logger, tmp_project):
        """Test graceful handling when ChromaDB is unavailable."""
        with patch("backend.utils.core.automatic_learning.chromadb", None):
            indexer = LearningIndexer(
                logger=mock_logger,
                project_root=tmp_project,
            )

            # Should handle None chromadb gracefully
            assert indexer.client is None
            assert indexer.collection is None


class TestAutomaticLearningSystem:
    """Test AutomaticLearningSystem."""

    def test_learning_system_initialization(self, mock_logger, tmp_project):
        """Test system initialization."""
        system = AutomaticLearningSystem(
            logger=mock_logger,
            project_root=tmp_project,
        )

        assert system.analyzer is not None
        assert system.indexer is not None

    def test_process_correction(self, mock_logger, tmp_project):
        """Test processing a correction end-to-end."""
        system = AutomaticLearningSystem(
            logger=mock_logger,
            project_root=tmp_project,
        )

        success = system.process_correction(
            error_message="NameError: name 'x' is not defined",
            error_type="NameError",
            file_path="main.py",
            language="python",
            initial_code="print(x)",
            corrected_code="x = 42\nprint(x)",
            correction_steps=["Added variable definition"],
            success_metrics={"syntax_valid": True, "runtime_valid": True},
            phase="generation",
            project_name="test_proj",
        )

        assert isinstance(success, bool)

    def test_get_suggestions_for_error(self, mock_logger, tmp_project):
        """Test getting suggestions for an error."""
        system = AutomaticLearningSystem(
            logger=mock_logger,
            project_root=tmp_project,
        )

        # Process one correction first
        system.process_correction(
            error_message="NameError: name 'x' is not defined",
            error_type="NameError",
            file_path="main.py",
            language="python",
            initial_code="print(x)",
            corrected_code="x = 42\nprint(x)",
            correction_steps=["Added definition"],
            success_metrics={"valid": True},
            phase="generation",
            project_name="proj1",
        )

        # Get suggestions for similar error
        suggestions = system.get_suggestions_for_error(
            error_message="NameError: name 'y' is not defined",
            language="python",
        )

        assert isinstance(suggestions, list)

    def test_generate_learning_report(self, mock_logger, tmp_project):
        """Test generating learning report."""
        system = AutomaticLearningSystem(
            logger=mock_logger,
            project_root=tmp_project,
        )

        # Process some corrections
        for i in range(3):
            system.process_correction(
                error_message=f"Error {i}",
                error_type="TestError",
                file_path=f"file{i}.py",
                language="python",
                initial_code="old",
                corrected_code="new",
                correction_steps=["step"],
                success_metrics={},
                phase="test",
                project_name=f"proj{i}",
            )

        report = system.generate_learning_report()

        assert "total_patterns" in report
        assert isinstance(report["total_patterns"], int)
        assert "error_type_distribution" in report

    def test_learning_report_empty_project(self, mock_logger, tmp_project):
        """Test report generation with no patterns."""
        system = AutomaticLearningSystem(
            logger=mock_logger,
            project_root=tmp_project,
        )

        report = system.generate_learning_report()

        # Should handle empty state
        assert report["total_patterns"] == 0
        assert report["error_type_distribution"] == {}

    def test_concurrent_processing(self, mock_logger, tmp_project):
        """Test that corrections can be processed concurrently."""
        system = AutomaticLearningSystem(
            logger=mock_logger,
            project_root=tmp_project,
        )

        import threading

        results = []

        def process():
            success = system.process_correction(
                error_message="ConcurrentError",
                error_type="TestError",
                file_path="test.py",
                language="python",
                initial_code="bad",
                corrected_code="good",
                correction_steps=["fix"],
                success_metrics={},
                phase="test",
                project_name="concurrent_test",
            )
            results.append(success)

        threads = [threading.Thread(target=process) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should complete successfully
        assert len(results) == 3
        assert all(isinstance(r, bool) for r in results)
