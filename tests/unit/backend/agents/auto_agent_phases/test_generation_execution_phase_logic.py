import pytest
from pathlib import Path
from unittest.mock import MagicMock
from backend.agents.auto_agent_phases.generation_execution_phase import TestGenerationExecutionPhase as PhaseUnderTest


@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.logger = MagicMock()
    ctx.event_publisher = MagicMock()
    ctx.event_publisher.publish = MagicMock()
    ctx.event_publisher.publish_sync = MagicMock()
    ctx.group_files_by_language.return_value = {"python": [("src/app.py", "print(1)")]}
    ctx.test_generator = MagicMock()
    ctx.test_generator.generate_tests = MagicMock()
    ctx.test_generator.generate_integration_tests = MagicMock(return_value=("", "", ".py"))
    ctx.file_manager = MagicMock()
    ctx.get_test_file_path.return_value = "tests/test_app.py"
    # Added to fix error in internals test
    ctx.error_knowledge_base = MagicMock()
    ctx._is_small_model.return_value = False
    return ctx


@pytest.fixture
def phase_instance(mock_context):
    return PhaseUnderTest(mock_context)


def test_execute_test_generation_success(phase_instance, mock_context):
    mock_context.test_generator.generate_tests.return_value = "def test_app(): pass"
    mock_context.test_generator.execute_tests.return_value = {"success": True, "output": "...", "failures": []}
    mock_context.test_generator.generate_integration_tests.return_value = ("", "", ".py")

    generated_files = {"src/app.py": "print(1)"}
    project_root = Path("/tmp/proj")

    res_files, _, _ = phase_instance.execute("desc", "name", project_root, "readme", {}, generated_files)

    assert "tests/test_app.py" in res_files
    assert res_files["tests/test_app.py"] == "def test_app(): pass"
    assert mock_context.test_generator.generate_tests.called
    assert mock_context.test_generator.execute_tests.called


def test_execute_fails_if_no_tests_generated(phase_instance, mock_context):
    mock_context.test_generator.generate_tests.return_value = None
    mock_context.test_generator.generate_integration_tests.return_value = ("", "", ".py")

    with pytest.raises(RuntimeError, match="MVP Requirement Failed"):
        phase_instance.execute("desc", "name", Path("/tmp"), "readme", {}, {"a.py": ""})
