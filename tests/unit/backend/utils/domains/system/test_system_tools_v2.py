import pytest
from unittest.mock import MagicMock, patch
from backend.utils.domains.system.system_tools import SystemTools

class TestSystemToolsUnit:
    """
    Unit tests for SystemTools to ensure inputs/outputs are correct.
    """

    @pytest.fixture
    def mock_deps(self):
        return {
            "exec": MagicMock(),
            "file_manager": MagicMock(),
            "logger": MagicMock(),
            "agent": MagicMock()
        }

    @pytest.fixture
    def system_tools(self, mock_deps):
        return SystemTools(
            command_executor=mock_deps["exec"],
            file_manager=mock_deps["file_manager"],
            logger=mock_deps["logger"],
            agent_instance=mock_deps["agent"]
        )

    def test_get_system_info_success(self, system_tools):
        """Validates that get_system_info (psutil) returns correct structure."""
        with patch('psutil.virtual_memory') as mock_vm, \
             patch('psutil.cpu_count') as mock_cpu, \
             patch('platform.system') as mock_sys, \
             patch('psutil.swap_memory') as mock_swap, \
             patch('psutil.boot_time') as mock_boot, \
             patch('psutil.cpu_freq') as mock_freq:

            # Setup mocks
            mock_vm.return_value.total = 16000000000
            mock_vm.return_value.available = 8000000000
            mock_vm.return_value.used = 8000000000
            mock_vm.return_value.free = 8000000000
            mock_vm.return_value.percent = 50.0

            mock_swap.return_value.total = 4000000000
            mock_swap.return_value.free = 2000000000

            mock_cpu.return_value = 8
            mock_sys.return_value = "Windows"
            mock_boot.return_value = 1600000000
            mock_freq.return_value.current = 3000

            result = system_tools.get_system_info()

            assert result["ok"] is True
            assert "result" in result
            assert result["result"]["os"]["system"] == "Windows"
            assert result["result"]["memory"]["total_bytes"] == 16000000000
            assert result["result"]["cpu"]["logical_cores"] == 8

    def test_list_processes_structure(self, system_tools, mock_deps):
        """Validates list_processes input/output and platform command branching."""
        system_tools.os_type = "Windows"
        mock_deps["exec"].execute.return_value.success = True
        mock_deps["exec"].execute.return_value.stdout = '[{"ProcessName": "python", "Id": 1234}]'

        result = system_tools.list_processes()

        assert result["ok"] is True
        assert "python" in str(result["result"])

    def test_install_package_pip(self, system_tools, mock_deps):
        """Validates install_package correctly formats pip command."""
        mock_deps["exec"].execute.return_value.success = True

        result = system_tools.install_package("requests", "pip")

        assert result["ok"] is True
        args, _ = mock_deps["exec"].execute.call_args
        assert "pip install" in args[0]
        assert "requests" in args[0]
