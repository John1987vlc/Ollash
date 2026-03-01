import pytest
from unittest.mock import MagicMock, patch
from backend.utils.domains.system.scripting_tools import ScriptingTools


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def scripting_tools(mock_logger):
    # Mocking ScriptingSandbox inside ScriptingTools
    with patch("backend.utils.domains.system.scripting_tools.ScriptingSandbox") as MockSandbox:
        tools = ScriptingTools(mock_logger)
        tools.sandbox = MockSandbox.return_value
        tools.sandbox._is_active = False  # Default state
        return tools


def test_init_environment(scripting_tools):
    scripting_tools.sandbox.start.return_value = None
    result = scripting_tools.init_environment()
    assert result["ok"] is True
    scripting_tools.sandbox.start.assert_called_once()


def test_write_script_auto_starts_sandbox(scripting_tools):
    scripting_tools.sandbox._is_active = False

    result = scripting_tools.write_script("test.sh", "echo hi")

    assert result["ok"] is True
    scripting_tools.sandbox.start.assert_called_once()
    scripting_tools.sandbox.write_file.assert_called_with("test.sh", "echo hi")
    scripting_tools.sandbox.execute_command.assert_called_with(["chmod", "+x", "test.sh"])


def test_execute_script_success(scripting_tools):
    scripting_tools.sandbox._is_active = True
    scripting_tools.sandbox.execute_command.return_value = {
        "success": True,
        "exit_code": 0,
        "stdout": "output",
        "stderr": "",
    }

    result = scripting_tools.execute_script("script.sh")

    assert result["ok"] is True
    assert result["result"]["stdout"] == "output"
    # Verify command construction
    scripting_tools.sandbox.execute_command.assert_called_with(["./script.sh"])


def test_execute_script_powershell(scripting_tools):
    scripting_tools.sandbox._is_active = True
    scripting_tools.sandbox.execute_command.return_value = {"success": True}

    scripting_tools.execute_script("script.ps1")

    scripting_tools.sandbox.execute_command.assert_called_with(["pwsh", "-File", "script.ps1"])


def test_execute_script_not_initialized(scripting_tools):
    scripting_tools.sandbox._is_active = False
    result = scripting_tools.execute_script("script.sh")
    assert result["ok"] is False
    assert "Sandbox not initialized" in result["error"]


def test_cleanup_environment(scripting_tools):
    result = scripting_tools.cleanup_environment()
    assert result["ok"] is True
    scripting_tools.sandbox.stop.assert_called_once()
