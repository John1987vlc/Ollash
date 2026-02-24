import pytest
from unittest.mock import MagicMock
from backend.utils.domains.network.network_tools import NetworkTools

class TestNetworkToolsUnit:
    """
    Unit tests for NetworkTools to ensure inputs/outputs are correct.
    """

    @pytest.fixture
    def mock_deps(self):
        return {
            "exec": MagicMock(),
            "logger": MagicMock()
        }

    @pytest.fixture
    def network_tools(self, mock_deps):
        return NetworkTools(
            command_executor=mock_deps["exec"],
            logger=mock_deps["logger"]
        )

    def test_ping_host_success(self, network_tools, mock_deps):
        """Validates ping_host formats command correctly and parses success."""
        mock_deps["exec"].execute.return_value.success = True
        mock_deps["exec"].execute.return_value.stdout = "Reply from 8.8.8.8..."

        result = network_tools.ping_host("8.8.8.8", count=2)

        assert result["ok"] is True
        args, _ = mock_deps["exec"].execute.call_args
        assert "8.8.8.8" in args[0]
        # Check platform specific flag (Windows uses -n, Linux -c)
        if network_tools.os_type == "Windows":
            assert "-n 2" in args[0]
        else:
            assert "-c 2" in args[0]

    def test_list_active_connections(self, network_tools, mock_deps):
        """Validates netstat usage."""
        mock_deps["exec"].execute.return_value.success = True
        mock_deps["exec"].execute.return_value.stdout = "TCP 0.0.0.0:80 LISTENING"

        result = network_tools.list_active_connections()

        assert result["ok"] is True
        args, _ = mock_deps["exec"].execute.call_args
        assert "netstat" in args[0]

    def test_check_port_status(self, network_tools, mock_deps):
        """Validates port checking logic (usually via Test-NetConnection or nc)."""
        mock_deps["exec"].execute.return_value.success = True
        mock_deps["exec"].execute.return_value.stdout = "TcpTestSucceeded : True"

        result = network_tools.check_port_status("localhost", 8080)

        assert result["ok"] is True
        assert result["result"]["status"] == "open"
