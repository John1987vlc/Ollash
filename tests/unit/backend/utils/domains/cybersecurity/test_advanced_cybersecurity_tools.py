import pytest
from pathlib import Path
from unittest.mock import MagicMock
from backend.utils.domains.cybersecurity.advanced_cybersecurity_tools import AdvancedCybersecurityTools
from backend.utils.core.command_executor import ExecutionResult

@pytest.fixture
def mock_exec():
    return MagicMock()

@pytest.fixture
def mock_files(tmp_path):
    mock = MagicMock()
    mock.root = tmp_path
    return mock

@pytest.fixture
def mock_logger():
    return MagicMock()

@pytest.fixture
def adv_tools(mock_exec, mock_files, mock_logger):
    return AdvancedCybersecurityTools(mock_exec, mock_files, mock_logger)

class TestAdvancedCybersecurityTools:
    def test_assess_attack_surface_linux(self, adv_tools):
        adv_tools.os_type = "Linux"
        result = adv_tools.assess_attack_surface()
        assert result["ok"] is True
        assert result["result"]["overall_risk_level"] == "low"

    def test_detect_ioc_suspicious_process_linux(self, adv_tools, mock_exec):
        adv_tools.os_type = "Linux"
        mock_exec.execute.return_value = ExecutionResult(True, "user 123 0.0 0.0 nc.exe -l -p 4444", "", 0, "ps aux")
        
        result = adv_tools.detect_ioc()
        
        assert result["ok"] is True
        assert result["result"]["status"] == "iocs_detected"
        assert any(ioc["type"] == "suspicious_process" for ioc in result["result"]["iocs"])

    def test_analyze_permissions_linux_world_writable(self, adv_tools, mock_exec, tmp_path):
        adv_tools.os_type = "Linux"
        target = tmp_path / "unsafe.txt"
        target.touch()
        
        mock_exec.execute.return_value = ExecutionResult(True, "drwxrwxrwx 1 user group 0 Jan 1 00:00 directory", "", 0, "ls -ld")
        
        result = adv_tools.analyze_permissions(str(target))
        
        assert result["ok"] is True
        assert result["result"]["status"] == "permission_issues_detected"
        assert any("World-writable" in finding["finding"] for finding in result["result"]["findings"])

    def test_security_posture_score_windows(self, adv_tools):
        adv_tools.os_type = "Windows"
        result = adv_tools.security_posture_score()
        assert result["ok"] is True
        assert result["result"]["score"] == 65 # 70 - 5
        assert result["result"]["rating"] == "Fair"
