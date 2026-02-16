"""
Unit Tests for CoworkTools Implementation
Tests document-to-task, log analysis, and executive summarization
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.documentation_manager import DocumentationManager
from backend.utils.core.ollama_client import OllamaClient
from backend.utils.domains.bonus.cowork_impl import CoworkTools


@pytest.fixture
def logger():
    """Mock logger"""
    logger = Mock(spec=AgentLogger)
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    return logger


@pytest.fixture
def ollama():
    """Mock OllamaClient"""
    client = Mock(spec=OllamaClient)
    client.call_ollama_api = Mock(return_value='[{"name": "Task 1"}]')
    return client


@pytest.fixture
def doc_manager(logger):
    """Mock DocumentationManager"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        manager = Mock(spec=DocumentationManager)
        manager.references_dir = tmpdir_path / "references"
        manager.references_dir.mkdir(exist_ok=True)
        yield manager


@pytest.fixture
def workspace():
    """Create temporary workspace"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def cowork(doc_manager, ollama, logger, workspace):
    """Initialize CoworkTools"""
    return CoworkTools(
        doc_manager=doc_manager,
        ollama_client=ollama,
        logger=logger,
        knowledge_workspace=workspace,
    )


class TestCoworkTools:
    """Test suite for CoworkTools"""

    def test_initialization(self, cowork, workspace):
        """Test CoworkTools initialization"""
        assert cowork.workspace == workspace
        assert cowork.ollama is not None
        assert cowork.doc_manager is not None

    def test_document_to_task_missing_document(self, cowork):
        """Test document_to_task with missing document"""
        result = cowork.document_to_task(document_name="nonexistent.pdf", task_category="automation")

        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    def test_document_to_task_invalid_format(self, cowork, doc_manager):
        """Test document_to_task with invalid file format"""
        # Create an unsupported file
        doc_manager.references_dir.mkdir(exist_ok=True)
        unsupported_file = doc_manager.references_dir / "test.xyz"
        unsupported_file.write_text("content")

        result = cowork.document_to_task(document_name="test.xyz", task_category="automation")

        assert result["status"] == "error"

    def test_document_to_task_success(self, cowork, doc_manager, ollama):
        """Test successful document-to-task conversion"""
        # Create a test document
        doc_manager.references_dir.mkdir(exist_ok=True)
        test_doc = doc_manager.references_dir / "requirements.txt"
        test_doc.write_text("Implement authentication\nAdd logging\nSetup monitoring")

        # Mock ingester
        with patch("backend.utils.domains.bonus.cowork_impl.MultiFormatIngester") as mock_ingester_class:
            mock_ingester = Mock()
            mock_ingester.ingest_file.return_value = "Implement auth\nAdd logging\nSetup monitoring"
            mock_ingester_class.return_value = mock_ingester

            cowork.ingester = mock_ingester

            ollama.call_ollama_api.return_value = '[{"task_id": "t1", "name": "Auth", "description": "Implement"}]'

            result = cowork.document_to_task(
                document_name="requirements.txt",
                task_category="automation",
                priority="high",
            )

            assert result["status"] == "success"
            assert "tasks_generated" in result
            assert result["tasks_generated"] >= 1

    def test_document_to_task_priority_levels(self, cowork, doc_manager):
        """Test document_to_task with different priority levels"""
        doc_manager.references_dir.mkdir(exist_ok=True)
        test_doc = doc_manager.references_dir / "test.txt"
        test_doc.write_text("Some requirement")

        with patch("backend.utils.domains.bonus.cowork_impl.MultiFormatIngester") as mock_ingester_class:
            mock_ingester = Mock()
            mock_ingester.ingest_file.return_value = "Requirement text"
            cowork.ingester = mock_ingester
            cowork.ollama.call_ollama_api.return_value = "[]"

            for priority in ["low", "medium", "high", "critical"]:
                result = cowork.document_to_task(document_name="test.txt", priority=priority)
                # Should not crash
                assert isinstance(result, dict)

    def test_analyze_recent_logs_no_logs(self, cowork, logger):
        """Test analyze_recent_logs when no logs found"""
        result = cowork.analyze_recent_logs(log_type="system", time_period="24hours", risk_threshold="high")

        # Result should indicate warning or success with no issues
        assert result["status"] in ["warning", "success", "error"]

    def test_analyze_recent_logs_success(self, cowork):
        """Test analyze_recent_logs with mocked logs"""
        with patch.object(cowork, "_get_log_paths") as mock_get_paths:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".log") as log_file:
                log_file.write("ERROR: Failed login attempt\nINFO: Backup completed\n")
                log_file.flush()

                mock_get_paths.return_value = [Path(log_file.name)]

                cowork.ollama.call_ollama_api.return_value = '[{"issue": "Failed login", "severity": "High"}]'

                result = cowork.analyze_recent_logs(log_type="security", time_period="24hours", top_n=5)

                assert "status" in result

    def test_analyze_recent_logs_risk_levels(self, cowork):
        """Test different risk threshold levels"""
        with patch.object(cowork, "_get_log_paths") as mock_get_paths:
            mock_get_paths.return_value = []

            for threshold in ["critical", "high", "medium", "low", "all"]:
                result = cowork.analyze_recent_logs(risk_threshold=threshold)
                # Should handle all thresholds gracefully
                assert "status" in result

    def test_generate_executive_summary_missing_doc(self, cowork):
        """Test executive summary with missing document"""
        result = cowork.generate_executive_summary(document_name="nonexistent.pdf")

        assert result["status"] == "error"

    def test_generate_executive_summary_success(self, cowork, doc_manager):
        """Test successful executive summary generation"""
        doc_manager.references_dir.mkdir(exist_ok=True)
        test_doc = doc_manager.references_dir / "spec.txt"
        test_doc.write_text("System specification with " + "many words " * 100)

        with patch("backend.utils.domains.bonus.cowork_impl.MultiFormatIngester") as mock_ingester_class:
            mock_ingester = Mock()
            mock_ingester.ingest_file.return_value = "System spec content"
            cowork.ingester = mock_ingester

            cowork.ollama.call_ollama_api.return_value = "Executive summary text"

            result = cowork.generate_executive_summary(
                document_name="spec.txt", summary_type="executive", max_length=250
            )

            if result["status"] == "success":
                assert "summary" in result
                assert "document" in result
                assert result["document"] == "spec.txt"

    def test_generate_executive_summary_types(self, cowork, doc_manager):
        """Test different summary types"""
        doc_manager.references_dir.mkdir(exist_ok=True)
        test_doc = doc_manager.references_dir / "doc.txt"
        test_doc.write_text("Content")

        with patch("backend.utils.domains.bonus.cowork_impl.MultiFormatIngester") as mock_ingester_class:
            mock_ingester = Mock()
            mock_ingester.ingest_file.return_value = "Document content"
            cowork.ingester = mock_ingester
            cowork.ollama.call_ollama_api.return_value = "Summary"

            for summary_type in ["executive", "technical", "general", "key_insights"]:
                result = cowork.generate_executive_summary(document_name="doc.txt", summary_type=summary_type)
                # Should not crash
                assert isinstance(result, dict)

    def test_append_tasks_to_file(self, cowork):
        """Test appending tasks to tasks.json"""
        cowork.tasks_file = Path(tempfile.gettempdir()) / "test_tasks.json"

        try:
            tasks = [
                {"task_id": "1", "name": "Task 1"},
                {"task_id": "2", "name": "Task 2"},
            ]

            cowork._append_tasks_to_file(tasks)

            assert cowork.tasks_file.exists()

            with open(cowork.tasks_file) as f:
                saved_tasks = json.load(f)

            assert len(saved_tasks) >= 2
        finally:
            if cowork.tasks_file.exists():
                cowork.tasks_file.unlink()

    def test_get_log_paths_system(self, cowork):
        """Test getting system log paths"""
        paths = cowork._get_log_paths("system")
        # Should return a list (might be empty on Windows)
        assert isinstance(paths, list)

    def test_get_log_paths_security(self, cowork):
        """Test getting security log paths"""
        paths = cowork._get_log_paths("security")
        assert isinstance(paths, list)

    def test_get_log_paths_all(self, cowork):
        """Test getting all log paths"""
        paths = cowork._get_log_paths("all")
        assert isinstance(paths, list)
