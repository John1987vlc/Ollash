import pytest
import subprocess
from unittest.mock import MagicMock, patch, AsyncMock
from backend.utils.core.command_executor import CommandExecutor, SandboxLevel, ExecutionResult


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def mock_policy():
    policy = MagicMock()
    policy.is_command_allowed.return_value = True
    return policy


@pytest.fixture
def executor(tmp_path, mock_logger, mock_policy):
    return CommandExecutor(
        working_dir=str(tmp_path), sandbox=SandboxLevel.NONE, logger=mock_logger, policy_manager=mock_policy
    )


class TestCommandExecutor:
    """Test suite for CommandExecutor with isolation from real OS commands."""

    def test_execute_success(self, executor):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "output"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            res = executor.execute("echo hello")

            assert res.success is True
            assert res.stdout == "output"
            mock_run.assert_called_once()

    def test_execute_failure(self, executor):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error message"

        with patch("subprocess.run", return_value=mock_result):
            res = executor.execute("false_command")
            assert res.success is False
            assert res.return_code == 1
            assert "error message" in res.stderr

    def test_execute_timeout(self, executor):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="test", timeout=1)):
            res = executor.execute("sleep 10", timeout=1)
            assert res.success is False
            assert res.return_code == -1
            assert "Timeout" in res.stderr

    def test_sandbox_strict_denial(self, executor, mock_policy):
        executor.sandbox = SandboxLevel.STRICT
        mock_policy.is_command_allowed.return_value = False

        res = executor.execute("rm -rf /")
        assert res.success is False
        assert "no permitido" in res.stderr
        mock_policy.is_command_allowed.assert_called_once()

    def test_pre_validate_typo(self, executor):
        res = executor.execute("pyton --version")
        assert res.success is False
        assert "Typo detected" in res.stderr
        assert "python" in res.stderr

    @pytest.mark.asyncio
    async def test_async_execute_success(self, executor):
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"async out", b"")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            res = await executor.async_execute(["echo", "hi"])

            assert res.success is True
            assert res.stdout == "async out"
            mock_exec.assert_called_once()

    def test_execute_python_safety_wrapper(self, executor):
        with patch.object(executor, "execute") as mock_exec:
            executor.execute_python("print('test')")
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args[0][0]
            assert "python" in call_args
            assert "print('test')" in call_args

    def test_get_python_packages(self, executor):
        mock_result = ExecutionResult(True, "pkg1==1.0\npkg2==2.0", "", 0, "pip list")
        with patch.object(executor, "execute", return_value=mock_result):
            pkgs = executor.get_python_packages()
            assert pkgs == ["pkg1", "pkg2"]
