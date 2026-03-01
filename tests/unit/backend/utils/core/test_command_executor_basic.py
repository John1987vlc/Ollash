import pytest
from backend.utils.core.command_executor import CommandExecutor, SandboxLevel
from unittest.mock import MagicMock


@pytest.fixture
def executor():
    logger = MagicMock()
    return CommandExecutor(logger=logger, working_dir=".")


def test_execute_basic_command(executor):
    # 'echo' should work on both Windows and Linux
    # On Windows, subprocess.run(['echo', 'hello']) works if 'echo' is a built-in or via cmd
    import platform

    cmd = ["cmd", "/c", "echo hello"] if platform.system() == "Windows" else ["echo", "hello"]
    result = executor.execute(cmd)
    assert result.success is True
    assert "hello" in result.stdout.lower()
    assert result.return_code == 0


def test_execute_invalid_command(executor):
    result = executor.execute(["nonexistent_command_12345"])
    assert result.success is False
    assert result.return_code != 0


@pytest.mark.asyncio
async def test_async_execute_basic(executor):
    import platform

    cmd = ["cmd", "/c", "echo hello"] if platform.system() == "Windows" else ["echo", "hello"]
    result = await executor.async_execute(cmd)
    assert result.success is True
    assert "hello" in result.stdout.lower()


def test_sandbox_disallowed_command(executor):
    # Setup sandbox with a policy manager that denies everything
    policy_mock = MagicMock()
    policy_mock.is_command_allowed.return_value = False

    executor.sandbox = SandboxLevel.STRICT
    executor.policy_manager = policy_mock

    result = executor.execute(["rm", "-rf", "/"])
    assert result.success is False
    assert "no permitido" in result.stderr.lower()
