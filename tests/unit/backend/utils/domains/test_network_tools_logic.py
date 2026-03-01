import pytest
from unittest.mock import MagicMock
from backend.utils.domains.network.network_tools import NetworkTools
from backend.utils.domains.network.advanced_network_tools import AdvancedNetworkTools


@pytest.fixture
def mock_exec():
    executor = MagicMock()
    executor.execute.return_value = MagicMock(success=True, stdout="", stderr="")
    return executor


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def network_tools(mock_exec, mock_logger):
    return NetworkTools(mock_exec, mock_logger)


@pytest.fixture
def advanced_network_tools(mock_exec, mock_logger):
    return AdvancedNetworkTools(mock_exec, mock_logger)


class TestNetworkTools:
    def test_ping_host_linux_success(self, network_tools, mock_exec):
        network_tools.os_type = "Linux"
        mock_exec.execute.return_value = MagicMock(
            success=True,
            stdout="""4 packets transmitted, 4 received, 0% packet loss, time 3003ms
rtt min/avg/max/mdev = 10.123/15.456/20.789/2.000 ms""",
        )

        result = network_tools.ping_host("google.com")

        assert result["ok"] is True
        assert result["result"]["packets_received"] == 4
        assert result["result"]["avg_rtt_ms"] == 15.456
        assert result["result"]["packet_loss_percent"] == 0.0

    def test_ping_host_windows_success(self, network_tools, mock_exec):
        network_tools.os_type = "Windows"
        mock_exec.execute.return_value = MagicMock(
            success=True,
            stdout="""Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),
Minimum = 10ms, Maximum = 20ms, Average = 15ms""",
        )

        result = network_tools.ping_host("google.com")

        assert result["ok"] is True
        assert result["result"]["packets_received"] == 4
        assert result["result"]["avg_rtt_ms"] == 15
        assert result["result"]["packet_loss_percent"] == 0

    def test_check_port_status_linux_open(self, network_tools, mock_exec):
        network_tools.os_type = "Linux"
        mock_exec.execute.return_value = MagicMock(
            success=True, stdout="Connection to 127.0.0.1 80 port [tcp/http] succeeded!", stderr=""
        )

        result = network_tools.check_port_status("127.0.0.1", 80)

        assert result["ok"] is True
        assert result["result"]["status"] == "open"

    def test_list_active_connections(self, network_tools, mock_exec):
        mock_exec.execute.return_value = MagicMock(
            success=True,
            stdout="""Proto Local Address          Foreign Address        State
TCP   127.0.0.1:8000         0.0.0.0:0              LISTENING""",
        )

        result = network_tools.list_active_connections()

        assert result["ok"] is True
        assert len(result["result"]["connections"]) == 1
        assert result["result"]["connections"][0]["protocol"] == "TCP"
        assert result["result"]["connections"][0]["state"] == "LISTENING"


class TestAdvancedNetworkTools:
    def test_analyze_network_latency_linux_success(self, advanced_network_tools, mock_exec):
        advanced_network_tools.os_type = "Linux"
        mock_exec.execute.side_effect = [
            MagicMock(
                success=True,
                stdout="""4 packets transmitted, 4 received, 0% packet loss
rtt min/avg/max/mdev = 10/15/20/2 ms""",
            ),
            MagicMock(
                success=True,
                stdout=""" 1  router (192.168.1.1) 1.0 ms
 2  isp (1.2.3.4) 10.0 ms""",
            ),
        ]

        result = advanced_network_tools.analyze_network_latency("google.com")

        assert result["ok"] is True
        assert result["result"]["data"]["packet_loss_percent"] == 0.0
        assert len(result["result"]["data"]["route_hops"]) == 2

    def test_detect_unexpected_services_linux_nmap(self, advanced_network_tools, mock_exec):
        advanced_network_tools.os_type = "Linux"
        mock_exec.execute.return_value = MagicMock(
            success=True, stdout="Host: 192.168.1.1 () Ports: 22/open/tcp//ssh///, 80/open/tcp//http///"
        )

        result = advanced_network_tools.detect_unexpected_services("192.168.1.1", [80])

        assert result["ok"] is True
        assert len(result["result"]["unexpected_services"]) == 1
        assert result["result"]["unexpected_services"][0]["port"] == 22

    def test_map_internal_network_linux(self, advanced_network_tools, mock_exec):
        advanced_network_tools.os_type = "Linux"
        mock_exec.execute.side_effect = [
            MagicMock(success=True, stdout="inet 192.168.1.10/24 brd 192.168.1.255 scope global eth0"),
            MagicMock(success=True, stdout="? (192.168.1.1) at 00:11:22:33:44:55 [ether] on eth0"),
        ]

        result = advanced_network_tools.map_internal_network()

        assert result["ok"] is True
        assert result["result"]["subnet"] == "192.168.1.10/24"
        assert len(result["result"]["hosts_found"]) == 1
        assert result["result"]["hosts_found"][0]["ip"] == "192.168.1.1"
