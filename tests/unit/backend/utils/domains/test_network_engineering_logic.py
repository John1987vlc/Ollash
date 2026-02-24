import pytest
from unittest.mock import MagicMock, patch
from backend.utils.domains.network.network_engineering_tools import NetworkEngineeringTools
from backend.utils.domains.network.network_sandbox_tools import NetworkSandboxTools

@pytest.fixture
def mock_logger():
    return MagicMock()

@pytest.fixture
def eng_tools(mock_logger):
    return NetworkEngineeringTools(mock_logger)

class TestNetworkEngineeringTools:
    def test_calculate_subnets_basic(self, eng_tools):
        result = eng_tools.calculate_subnets("192.168.1.0/24", 26)
        assert result["ok"] is True
        assert result["result"]["total_subnets"] == 4
        assert result["result"]["subnets"][0]["network"] == "192.168.1.0/26"
        assert result["result"]["subnets"][0]["total_hosts"] == 62

    def test_calculate_subnets_invalid(self, eng_tools):
        result = eng_tools.calculate_subnets("invalid_cidr", 24)
        assert result["ok"] is False
        assert "error" in result

    def test_audit_cisco_config_vulnerable(self, eng_tools):
        config = """
        interface GigabitEthernet0/1
         no service password-encryption
         line vty 0 4
          transport input telnet
        """
        result = eng_tools.audit_cisco_config(config)
        assert result["ok"] is True
        assert result["result"]["status"] == "vulnerable"
        issues = [f["issue"] for f in result["result"]["findings"]]
        assert "No Password Encryption" in issues
        assert "Telnet Enabled" in issues

    def test_audit_cisco_config_secure(self, eng_tools):
        config = "service password-encryption\nenable secret 5 $abc..."
        result = eng_tools.audit_cisco_config(config)
        assert result["ok"] is True
        assert result["result"]["status"] == "secure"

@pytest.fixture
def sandbox_tools(mock_logger):
    with patch("backend.utils.domains.network.network_sandbox_tools.NetworkSandbox") as MockSandbox:
        tools = NetworkSandboxTools(mock_logger)
        tools.sandbox = MockSandbox.return_value
        tools.sandbox._is_active = False
        return tools

class TestNetworkSandboxTools:
    def test_run_scapy_simulation(self, sandbox_tools):
        sandbox_tools.sandbox.run_scapy_script.return_value = {"success": True, "stdout": "Sent 1 packets."}

        result = sandbox_tools.run_scapy("send(IP(dst='8.8.8.8')/ICMP())")

        assert result["ok"] is True
        sandbox_tools.sandbox.start.assert_called_once()
        sandbox_tools.sandbox.run_scapy_script.assert_called()

    def test_nmap_scan(self, sandbox_tools):
        sandbox_tools.sandbox.run_nmap_scan.return_value = {"success": True, "stdout": "Host is up"}

        result = sandbox_tools.nmap_scan("127.0.0.1")

        assert result["ok"] is True
        sandbox_tools.sandbox.run_nmap_scan.assert_called_with("127.0.0.1", "-F")
