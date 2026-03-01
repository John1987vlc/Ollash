import pytest
import json
from unittest.mock import MagicMock, patch
from backend.utils.domains.system.system_tools import SystemTools
from backend.utils.domains.system.advanced_system_tools import AdvancedSystemTools


@pytest.fixture
def mock_exec():
    executor = MagicMock()
    executor.execute.return_value = MagicMock(success=True, stdout="{}", stderr="")
    return executor


@pytest.fixture
def mock_files():
    files = MagicMock()
    files.root = MagicMock()
    return files


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.model_health_monitor = MagicMock()
    return agent


@pytest.fixture
def system_tools(mock_exec, mock_files, mock_logger, mock_agent):
    return SystemTools(mock_exec, mock_files, mock_logger, mock_agent)


@pytest.fixture
def advanced_system_tools(mock_exec, mock_logger):
    return AdvancedSystemTools(mock_exec, mock_logger)


class TestSystemTools:
    def test_get_system_info_windows(self, system_tools, mock_exec):
        system_tools.os_type = "Windows"
        mock_exec.execute.return_value = MagicMock(
            success=True, stdout=json.dumps({"CsName": "TEST-PC", "OsName": "Windows 11"})
        )

        result = system_tools.get_system_info()

        assert result["ok"] is True
        assert result["result"]["info"]["OsName"] == "Windows 11"
        mock_exec.execute.assert_called()

    def test_get_system_info_linux(self, system_tools, mock_exec):
        system_tools.os_type = "Linux"
        # Linux returns multiple JSON objects concatenated
        mock_exec.execute.return_value = MagicMock(success=True, stdout='{"hostname": "test-linux"}{"cpu": "intel"}')

        result = system_tools.get_system_info()

        assert result["ok"] is True
        assert result["result"]["info"]["hostname"] == "test-linux"
        assert result["result"]["info"]["cpu"] == "intel"

    def test_list_processes_linux(self, system_tools, mock_exec):
        system_tools.os_type = "Linux"
        # ps aux header: USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND
        mock_exec.execute.return_value = MagicMock(
            success=True,
            stdout="""USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root         1  0.1  0.1  10000  1000 ?        Ss   00:00   0:01 /sbin/init
user       123  5.0  2.0  50000  5000 pts/0    S    00:01   0:00 python app.py""",
        )

        result = system_tools.list_processes()

        assert result["ok"] is True
        assert len(result["result"]["processes"]) == 2
        assert result["result"]["processes"][1]["pid"] == 123
        assert result["result"]["processes"][1]["user"] == "user"

    def test_install_package_pip(self, system_tools, mock_exec):
        result = system_tools.install_package("requests", "pip")

        assert result["ok"] is True
        assert result["result"]["package"] == "requests"
        mock_exec.execute.assert_called_with("pip install requests", timeout=300)

    def test_read_log_file(self, system_tools, mock_files):
        # Mock file reading
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        system_tools.files.root.__truediv__.return_value = mock_path

        # Simpler: patch open in the module
        with patch("backend.utils.domains.system.system_tools.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.readlines.return_value = ["line1\n", "line2\n", "error\n"]

            result = system_tools.read_log_file("test.log", lines=2)

            assert result["ok"] is True
            assert result["result"]["lines_read"] == 2
            assert "error" in result["result"]["content"]


class TestAdvancedSystemTools:
    def test_check_disk_health_linux(self, advanced_system_tools, mock_exec):
        advanced_system_tools.os_type = "Linux"
        mock_exec.execute.side_effect = [
            MagicMock(success=True, stdout="Filesystem Size Used Avail Use% Mounted on\n/dev/sda1 20G 10G 9G 50% /"),
            MagicMock(
                success=True, stdout="Filesystem Inodes IUsed IFree IUse% Mounted on\n/dev/sda1 1M 100K 900K 10% /"
            ),
        ]

        result = advanced_system_tools.check_disk_health()

        assert result["ok"] is True
        assert result["result"]["status"] == "healthy"
        assert result["result"]["partitions"][0]["usage_percent"] == 50
        assert result["result"]["partitions"][0]["inodes_usage_percent"] == 10

    def test_monitor_resource_spikes_cpu_linux(self, advanced_system_tools, mock_exec):
        advanced_system_tools.os_type = "Linux"
        mock_exec.execute.return_value = MagicMock(success=True, stdout="Cpu(s): 10.0%us, 5.0%sy, 0.0%ni, 80.0%id, ...")

        result = advanced_system_tools.monitor_resource_spikes("cpu")

        assert result["ok"] is True
        assert result["result"]["current_usage"]["current_value"] == 20.0  # 100 - 80 idle

    def test_analyze_startup_services_linux(self, advanced_system_tools, mock_exec):
        advanced_system_tools.os_type = "Linux"
        mock_exec.execute.return_value = MagicMock(
            success=True, stdout="UNIT FILE STATE\ndocker.service enabled\nnginx.service enabled"
        )

        result = advanced_system_tools.analyze_startup_services()

        assert result["ok"] is True
        assert len(result["result"]["services"]) == 2
        assert result["result"]["services"][0]["name"] == "docker.service"
