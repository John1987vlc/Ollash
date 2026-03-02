import pytest
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
    def test_get_system_info_returns_ok(self, system_tools):
        import unittest.mock as um

        mock_mem = MagicMock(total=8 * 2**30, available=4 * 2**30, used=4 * 2**30, free=4 * 2**30, percent=50.0)
        mock_swap = MagicMock(total=2 * 2**30, free=1 * 2**30)
        mock_freq = MagicMock(current=2400.0)

        with (
            um.patch("psutil.virtual_memory", return_value=mock_mem),
            um.patch("psutil.swap_memory", return_value=mock_swap),
            um.patch("psutil.cpu_count", return_value=4),
            um.patch("psutil.cpu_freq", return_value=mock_freq),
            um.patch("psutil.boot_time", return_value=0.0),
            um.patch("platform.system", return_value="Linux"),
            um.patch("platform.release", return_value="5.15"),
            um.patch("platform.version", return_value="#1 SMP"),
            um.patch("platform.architecture", return_value=("64bit", "")),
            um.patch("platform.machine", return_value="x86_64"),
            um.patch("platform.node", return_value="test-host"),
        ):
            result = system_tools.get_system_info()

        assert result["ok"] is True
        assert result["result"]["os"]["system"] == "Linux"
        assert result["result"]["memory"]["percent_used"] == 50.0
        assert result["result"]["cpu"]["logical_cores"] == 4

    def test_get_system_info_psutil_error(self, system_tools):
        with patch("psutil.virtual_memory", side_effect=RuntimeError("psutil fail")):
            result = system_tools.get_system_info()
        assert result["ok"] is False

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
