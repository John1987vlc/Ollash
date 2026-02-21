import pytest
import hashlib
from unittest.mock import MagicMock
from backend.utils.domains.cybersecurity.cybersecurity_tools import CybersecurityTools
from backend.utils.core.command_executor import ExecutionResult


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def mock_executor():
    return MagicMock()


@pytest.fixture
def mock_file_manager(tmp_path):
    mock = MagicMock()
    mock.root = tmp_path
    return mock


@pytest.fixture
def tools(mock_executor, mock_file_manager, mock_logger):
    return CybersecurityTools(command_executor=mock_executor, file_manager=mock_file_manager, logger=mock_logger)


class TestCybersecurityTools:
    """Test suite for specialized cybersecurity domain tools."""

    def test_scan_ports_linux_success(self, tools, mock_executor):
        # Force non-Windows for this test to trigger nmap logic
        tools.os_type = "Linux"

        mock_stdout = """
PORT     STATE SERVICE
22/tcp   open  ssh
80/tcp   open  http
443/tcp  closed https
"""
        mock_executor.execute.return_value = ExecutionResult(True, mock_stdout, "", 0, "nmap")

        result = tools.scan_ports(host="localhost")

        assert result["ok"] is True
        ports = result["result"]["ports"]
        assert len(ports) == 3
        assert ports[0]["port"] == 22
        assert ports[0]["state"] == "open"

    def test_scan_ports_windows_success(self, tools, mock_executor):
        tools.os_type = "Windows"

        # Windows logic uses Test-NetConnection and concatenates JSON objects
        # The tool does: json_output = f"[{result.stdout.replace('}{', '},{')}]"
        mock_stdout = '{"TcpTestSucceeded": true, "Port": 80}{"TcpTestSucceeded": false, "Port": 443}'
        mock_executor.execute.return_value = ExecutionResult(True, mock_stdout, "", 0, "powershell")

        result = tools.scan_ports(host="127.0.0.1")

        assert result["ok"] is True
        ports = result["result"]["ports"]
        assert len(ports) == 2
        assert ports[0]["port"] == 80
        assert ports[0]["status"] == "open"
        assert ports[1]["status"] == "closed/filtered"

    def test_check_file_hash_success(self, tools, mock_file_manager, tmp_path):
        f = tmp_path / "secret.txt"
        content = b"my secret message"
        f.write_bytes(content)

        expected_sha = hashlib.sha256(content).hexdigest()

        result = tools.check_file_hash("secret.txt", algorithm="sha256")

        assert result["ok"] is True
        assert result["result"]["hash"] == expected_sha

    def test_analyze_security_log_anomalies(self, tools, mock_file_manager, tmp_path):
        log_file = tmp_path / "auth.log"
        log_content = "INFO: System start\nWARNING: Failed login attempt from 1.2.3.4\nERROR: Access Denied"
        log_file.write_text(log_content, encoding="utf-8")

        result = tools.analyze_security_log("auth.log")

        assert result["ok"] is True
        assert result["result"]["status"] == "anomalies_found"
        assert len(result["result"]["events"]) == 2  # WARNING and ERROR
        assert "Failed login" in result["result"]["events"][0]["context"]

    def test_recommend_security_hardening(self, tools):
        result = tools.recommend_security_hardening(os_type="Linux")
        assert result["ok"] is True
        assert len(result["result"]["recommendations"]) > 0
        assert "SSH" in str(result["result"]["recommendations"])
