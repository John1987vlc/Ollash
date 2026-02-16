"""
Unit tests for additional core modules: Part 3

Tests for:
- WasmSandbox & WasmTestRunner
- LoadSimulator
- DocTranslator
- PluginInterface & PluginManager
- GitPRTool
- AdvancedTriggerManager
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from backend.utils.core.advanced_trigger_manager import (
    AdvancedTriggerManager,
    CompositeTriggerCondition,
    LogicOperator,
    TriggerState,
)
from backend.utils.core.doc_translator import SUPPORTED_LANGUAGES, DocTranslator
from backend.utils.core.git_pr_tool import GitPRTool, PRResult
from backend.utils.core.load_simulator import LoadSimulator, LoadTestResult, ScriptBenchResult
from backend.utils.core.plugin_interface import OllashPlugin
from backend.utils.core.plugin_manager import PluginManager
from backend.utils.core.wasm_sandbox import SandboxInstance, TestResult, WasmSandbox, WasmTestRunner


# ============================================================================
# WasmSandbox & WasmTestRunner Tests
# ============================================================================


class TestWasmSandbox:
    """Tests for WasmSandbox class."""

    def test_init_with_unavailable_runtime(self):
        """Test WasmSandbox.__init__ with unavailable runtime (subprocess raises FileNotFoundError)."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            logger = MagicMock()
            sandbox = WasmSandbox(runtime="wasmtime", logger=logger)

            assert sandbox.runtime == "wasmtime"
            assert sandbox.is_available is False
            logger.info.assert_called_with("Wasm runtime 'wasmtime' not available, using fallback")

    def test_init_with_available_runtime(self):
        """Test WasmSandbox.__init__ with available runtime."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "wasmtime 1.0.0"

        with patch("subprocess.run", return_value=mock_result):
            logger = MagicMock()
            sandbox = WasmSandbox(runtime="wasmtime", logger=logger)

            assert sandbox.is_available is True
            logger.info.assert_called_with("Wasm runtime available: wasmtime wasmtime 1.0.0")

    def test_create_sandbox(self, tmp_path):
        """Test create_sandbox creates temp directory and returns SandboxInstance."""
        logger = MagicMock()

        with patch("subprocess.run", side_effect=FileNotFoundError):
            sandbox = WasmSandbox(runtime="wasmtime", logger=logger)

        with patch("tempfile.mkdtemp", return_value=str(tmp_path / "sandbox_test")):
            instance = sandbox.create_sandbox(allowed_dirs=[Path("/tmp")], memory_limit_mb=512)

            assert isinstance(instance, SandboxInstance)
            assert instance.memory_limit_mb == 512
            assert instance.runtime == "wasmtime"
            assert Path("/tmp") in instance.allowed_dirs
            assert instance.sandbox_id in sandbox._instances
            logger.info.assert_called()

    def test_destroy_sandbox(self, tmp_path):
        """Test destroy_sandbox cleans up temp directory."""
        logger = MagicMock()
        work_dir = tmp_path / "sandbox_cleanup"
        work_dir.mkdir()

        with patch("subprocess.run", side_effect=FileNotFoundError):
            sandbox = WasmSandbox(logger=logger)

        instance = SandboxInstance(
            sandbox_id="test123",
            work_dir=work_dir,
            allowed_dirs=[],
            memory_limit_mb=256,
            runtime="wasmtime",
        )
        sandbox._instances[instance.sandbox_id] = instance

        sandbox.destroy_sandbox(instance)

        assert instance.sandbox_id not in sandbox._instances
        logger.info.assert_called_with("Destroyed sandbox: test123")

    def test_destroy_all(self, tmp_path):
        """Test destroy_all cleans up all instances."""
        logger = MagicMock()

        with patch("subprocess.run", side_effect=FileNotFoundError):
            sandbox = WasmSandbox(logger=logger)

        # Create multiple instances
        instances = []
        for i in range(3):
            work_dir = tmp_path / f"sandbox_{i}"
            work_dir.mkdir()
            instance = SandboxInstance(
                sandbox_id=f"test{i}",
                work_dir=work_dir,
                allowed_dirs=[],
                memory_limit_mb=256,
                runtime="wasmtime",
            )
            sandbox._instances[instance.sandbox_id] = instance
            instances.append(instance)

        sandbox.destroy_all()

        assert len(sandbox._instances) == 0

    def test_is_available_property(self):
        """Test is_available property."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            sandbox = WasmSandbox()
            assert sandbox.is_available is False

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "wasmtime 1.0.0"

        with patch("subprocess.run", return_value=mock_result):
            sandbox = WasmSandbox()
            assert sandbox.is_available is True

    def test_sandbox_instance_to_dict(self, tmp_path):
        """Test SandboxInstance.to_dict serialization."""
        work_dir = tmp_path / "sandbox"
        instance = SandboxInstance(
            sandbox_id="abc123",
            work_dir=work_dir,
            allowed_dirs=[],
            memory_limit_mb=512,
            runtime="wasmtime",
        )

        result = instance.to_dict()

        assert result["sandbox_id"] == "abc123"
        assert result["work_dir"] == str(work_dir)
        assert result["memory_limit_mb"] == 512
        assert result["runtime"] == "wasmtime"

    def test_test_result_to_dict(self):
        """Test TestResult.to_dict serialization."""
        result = TestResult(
            success=True,
            exit_code=0,
            stdout="Test output" * 1000,  # Long output
            stderr="Error output" * 500,  # Long stderr
            duration_seconds=1.2345678,
            tests_run=10,
            tests_passed=8,
            tests_failed=2,
        )

        result_dict = result.to_dict()

        assert result_dict["success"] is True
        assert result_dict["exit_code"] == 0
        assert len(result_dict["stdout"]) <= 5000
        assert len(result_dict["stderr"]) <= 2000
        assert result_dict["duration_seconds"] == 1.235
        assert result_dict["tests_run"] == 10
        assert result_dict["tests_passed"] == 8
        assert result_dict["tests_failed"] == 2


class TestWasmTestRunner:
    """Tests for WasmTestRunner class."""

    @pytest.mark.asyncio
    async def test_run_tests_subprocess_fallback(self, tmp_path):
        """Test run_tests with subprocess fallback (Wasm not available)."""
        logger = MagicMock()

        with patch("subprocess.run", side_effect=FileNotFoundError):
            sandbox = WasmSandbox(logger=logger)

        runner = WasmTestRunner(sandbox=sandbox, logger=logger)

        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "test.py").write_text("print('test')")

        mock_subprocess_result = MagicMock()
        mock_subprocess_result.returncode = 0
        mock_subprocess_result.stdout = "5 passed"
        mock_subprocess_result.stderr = ""

        with patch("subprocess.run", return_value=mock_subprocess_result):
            with patch("shutil.copytree"):
                with patch("shutil.copy2"):
                    result = await runner.run_tests(project_root, "pytest", timeout=30)

        assert isinstance(result, TestResult)
        assert result.success is True
        assert result.exit_code == 0
        assert result.tests_passed == 5

    @pytest.mark.asyncio
    async def test_run_tests_timeout(self, tmp_path):
        """Test run_tests with timeout."""
        logger = MagicMock()

        with patch("subprocess.run", side_effect=FileNotFoundError):
            sandbox = WasmSandbox(logger=logger)

        runner = WasmTestRunner(sandbox=sandbox, logger=logger)

        project_root = tmp_path / "project"
        project_root.mkdir()

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pytest", 30)):
            with patch("shutil.copytree"):
                result = await runner.run_tests(project_root, "pytest", timeout=30)

        assert result.success is False
        assert result.exit_code == -1
        assert "timed out" in result.stderr


# ============================================================================
# LoadSimulator Tests
# ============================================================================


class TestLoadSimulator:
    """Tests for LoadSimulator class."""

    def test_load_test_result_success_rate(self):
        """Test LoadTestResult.success_rate property."""
        result = LoadTestResult(
            target="http://example.com",
            concurrent_users=10,
            duration_seconds=5.0,
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            avg_response_time_ms=50.0,
            min_response_time_ms=10.0,
            max_response_time_ms=200.0,
            p95_response_time_ms=150.0,
            requests_per_second=20.0,
        )

        assert result.success_rate == 0.95

    def test_load_test_result_success_rate_zero_requests(self):
        """Test LoadTestResult.success_rate with zero requests."""
        result = LoadTestResult(
            target="http://example.com",
            concurrent_users=10,
            duration_seconds=5.0,
            total_requests=0,
            successful_requests=0,
            failed_requests=0,
            avg_response_time_ms=0.0,
            min_response_time_ms=0.0,
            max_response_time_ms=0.0,
            p95_response_time_ms=0.0,
            requests_per_second=0.0,
        )

        assert result.success_rate == 0.0

    def test_load_test_result_to_dict(self):
        """Test LoadTestResult.to_dict serialization."""
        result = LoadTestResult(
            target="http://example.com",
            concurrent_users=10,
            duration_seconds=5.123456,
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            avg_response_time_ms=50.6789,
            min_response_time_ms=10.1234,
            max_response_time_ms=200.9876,
            p95_response_time_ms=150.5555,
            requests_per_second=20.4321,
            errors=["error1", "error2"],
        )

        result_dict = result.to_dict()

        assert result_dict["target"] == "http://example.com"
        assert result_dict["concurrent_users"] == 10
        assert result_dict["success_rate"] == 95.0
        assert result_dict["avg_response_time_ms"] == 50.68
        assert result_dict["min_response_time_ms"] == 10.12
        assert result_dict["max_response_time_ms"] == 200.99
        assert result_dict["p95_response_time_ms"] == 150.56
        assert result_dict["requests_per_second"] == 20.43
        assert result_dict["errors"] == ["error1", "error2"]

    def test_script_bench_result_to_dict(self):
        """Test ScriptBenchResult.to_dict serialization."""
        result = ScriptBenchResult(
            script_path="/path/to/script.py",
            iterations=10,
            total_time_seconds=15.123456,
            avg_time_seconds=1.512345,
            min_time_seconds=1.0,
            max_time_seconds=2.0,
            exit_codes=[0, 0, 0, 1, 0, 0, 0, 0, 0, 0],
            errors=["error1"],
        )

        result_dict = result.to_dict()

        assert result_dict["script_path"] == "/path/to/script.py"
        assert result_dict["iterations"] == 10
        assert result_dict["total_time_seconds"] == 15.123
        assert result_dict["avg_time_seconds"] == 1.512
        assert result_dict["min_time_seconds"] == 1.0
        assert result_dict["max_time_seconds"] == 2.0
        assert result_dict["success_rate"] == 90.0
        assert result_dict["errors"] == ["error1"]

    def test_generate_report_load_test_result(self):
        """Test generate_report for LoadTestResult."""
        command_executor = MagicMock()
        logger = MagicMock()
        simulator = LoadSimulator(command_executor, logger)

        results = [
            LoadTestResult(
                target="http://example.com",
                concurrent_users=10,
                duration_seconds=5.0,
                total_requests=100,
                successful_requests=95,
                failed_requests=5,
                avg_response_time_ms=50.0,
                min_response_time_ms=10.0,
                max_response_time_ms=200.0,
                p95_response_time_ms=150.0,
                requests_per_second=20.0,
            )
        ]

        report = simulator.generate_report(results)

        assert "# Performance Report" in report
        assert "## HTTP Load Test: http://example.com" in report
        assert "Concurrent users: 10" in report
        assert "Total requests: 100" in report
        assert "Success rate: 95.0%" in report
        assert "Avg response time: 50.0ms" in report
        assert "Requests/second: 20.0" in report

    def test_generate_report_script_bench_result(self):
        """Test generate_report for ScriptBenchResult."""
        command_executor = MagicMock()
        logger = MagicMock()
        simulator = LoadSimulator(command_executor, logger)

        results = [
            ScriptBenchResult(
                script_path="/path/to/script.py",
                iterations=10,
                total_time_seconds=15.0,
                avg_time_seconds=1.5,
                min_time_seconds=1.0,
                max_time_seconds=2.0,
                exit_codes=[0] * 10,
                errors=[],
            )
        ]

        report = simulator.generate_report(results)

        assert "# Performance Report" in report
        assert "## Script Benchmark: /path/to/script.py" in report
        assert "Iterations: 10" in report
        assert "Avg time: 1.500s" in report
        assert "Min/Max: 1.000s / 2.000s" in report
        assert "Success rate: 100%" in report

    def test_generate_report_mixed_results(self):
        """Test generate_report for mixed results."""
        command_executor = MagicMock()
        logger = MagicMock()
        simulator = LoadSimulator(command_executor, logger)

        results = [
            LoadTestResult(
                target="http://example.com",
                concurrent_users=5,
                duration_seconds=3.0,
                total_requests=50,
                successful_requests=48,
                failed_requests=2,
                avg_response_time_ms=25.0,
                min_response_time_ms=5.0,
                max_response_time_ms=100.0,
                p95_response_time_ms=75.0,
                requests_per_second=16.0,
            ),
            ScriptBenchResult(
                script_path="/test.py",
                iterations=5,
                total_time_seconds=7.5,
                avg_time_seconds=1.5,
                min_time_seconds=1.2,
                max_time_seconds=1.8,
                exit_codes=[0, 0, 0, 0, 0],
                errors=[],
            ),
        ]

        report = simulator.generate_report(results)

        assert "## HTTP Load Test: http://example.com" in report
        assert "## Script Benchmark: /test.py" in report


# ============================================================================
# DocTranslator Tests
# ============================================================================


class TestDocTranslator:
    """Tests for DocTranslator class."""

    def test_get_output_filename(self):
        """Test get_output_filename generates correct names."""
        llm_client = MagicMock()
        logger = MagicMock()
        translator = DocTranslator(llm_client, logger)

        assert translator.get_output_filename("README.md", "es") == "README.es.md"
        assert translator.get_output_filename("CONTRIBUTING.md", "fr") == "CONTRIBUTING.fr.md"
        assert translator.get_output_filename("docs/guide.md", "de") == "guide.de.md"

    def test_get_supported_languages(self):
        """Test get_supported_languages returns expected dict."""
        llm_client = MagicMock()
        logger = MagicMock()
        translator = DocTranslator(llm_client, logger)

        languages = translator.get_supported_languages()

        assert isinstance(languages, dict)
        assert languages["en"] == "English"
        assert languages["es"] == "Spanish"
        assert languages["fr"] == "French"
        assert languages["de"] == "German"
        assert languages["zh"] == "Chinese"

    def test_supported_languages_contains_expected_entries(self):
        """Test SUPPORTED_LANGUAGES contains expected entries."""
        assert "en" in SUPPORTED_LANGUAGES
        assert "es" in SUPPORTED_LANGUAGES
        assert "fr" in SUPPORTED_LANGUAGES
        assert "de" in SUPPORTED_LANGUAGES
        assert "pt" in SUPPORTED_LANGUAGES
        assert "zh" in SUPPORTED_LANGUAGES
        assert "ja" in SUPPORTED_LANGUAGES
        assert "ko" in SUPPORTED_LANGUAGES
        assert "ru" in SUPPORTED_LANGUAGES
        assert "ar" in SUPPORTED_LANGUAGES
        assert "it" in SUPPORTED_LANGUAGES
        assert "nl" in SUPPORTED_LANGUAGES

        assert SUPPORTED_LANGUAGES["en"] == "English"
        assert SUPPORTED_LANGUAGES["es"] == "Spanish"


# ============================================================================
# PluginInterface & PluginManager Tests
# ============================================================================


class ConcretePlugin(OllashPlugin):
    """Concrete implementation for testing."""

    def get_id(self) -> str:
        return "test_plugin"

    def get_name(self) -> str:
        return "Test Plugin"

    def get_version(self) -> str:
        return "1.0.0"

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "test_tool",
                    "description": "A test tool",
                    "parameters": {
                        "type": "object",
                        "properties": {"input": {"type": "string"}},
                        "required": ["input"],
                    },
                },
            }
        ]

    def get_toolset_configs(self) -> List[Dict[str, Any]]:
        return [
            {
                "toolset_id": "test_toolset",
                "class_path": "test.TestToolset",
                "init_args": {},
                "agent_types": ["orchestrator", "code"],
            }
        ]


class TestOllashPlugin:
    """Tests for OllashPlugin interface."""

    def test_concrete_plugin_implements_abstract_methods(self):
        """Test concrete OllashPlugin subclass must implement abstract methods."""
        plugin = ConcretePlugin()

        assert plugin.get_id() == "test_plugin"
        assert plugin.get_name() == "Test Plugin"
        assert plugin.get_version() == "1.0.0"
        assert len(plugin.get_tool_definitions()) == 1
        assert len(plugin.get_toolset_configs()) == 1

    def test_get_metadata(self):
        """Test OllashPlugin.get_metadata returns correct dict."""
        plugin = ConcretePlugin()
        metadata = plugin.get_metadata()

        assert metadata["id"] == "test_plugin"
        assert metadata["name"] == "Test Plugin"
        assert metadata["version"] == "1.0.0"
        assert "orchestrator" in metadata["agent_types"]
        assert "code" in metadata["agent_types"]
        assert isinstance(metadata["dependencies"], list)

    def test_get_agent_types(self):
        """Test OllashPlugin.get_agent_types derives from toolset configs."""
        plugin = ConcretePlugin()
        agent_types = plugin.get_agent_types()

        assert "orchestrator" in agent_types
        assert "code" in agent_types


class TestPluginManager:
    """Tests for PluginManager class."""

    def test_init_with_non_existent_dir(self, tmp_path):
        """Test PluginManager.__init__ with non-existent dir."""
        logger = MagicMock()
        plugins_dir = tmp_path / "nonexistent_plugins"

        manager = PluginManager(plugins_dir=plugins_dir, logger=logger)

        assert manager.plugins_dir == plugins_dir
        assert manager._loaded_plugins == {}

    def test_discover_with_missing_directory(self, tmp_path):
        """Test PluginManager.discover with missing directory returns empty."""
        logger = MagicMock()
        plugins_dir = tmp_path / "missing_plugins"

        manager = PluginManager(plugins_dir=plugins_dir, logger=logger)
        discovered = manager.discover()

        assert discovered == []
        logger.info.assert_called_with(f"Plugins directory not found: {plugins_dir}")

    def test_unload_plugin(self, tmp_path):
        """Test PluginManager.unload_plugin removes from loaded."""
        logger = MagicMock()
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        manager = PluginManager(plugins_dir=plugins_dir, logger=logger)

        # Manually add a plugin
        plugin = ConcretePlugin()
        manager._loaded_plugins[plugin.get_id()] = plugin

        assert "test_plugin" in manager._loaded_plugins

        manager.unload_plugin("test_plugin")

        assert "test_plugin" not in manager._loaded_plugins
        logger.info.assert_called_with("Unloaded plugin: test_plugin")

    def test_get_all_tool_definitions(self, tmp_path):
        """Test PluginManager.get_all_tool_definitions aggregates from loaded plugins."""
        logger = MagicMock()
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        manager = PluginManager(plugins_dir=plugins_dir, logger=logger)

        # Add multiple plugins
        plugin1 = ConcretePlugin()
        manager._loaded_plugins["plugin1"] = plugin1

        definitions = manager.get_all_tool_definitions()

        assert len(definitions) >= 1
        assert definitions[0]["type"] == "function"
        assert definitions[0]["function"]["name"] == "test_tool"

    def test_get_plugin_metadata(self, tmp_path):
        """Test PluginManager.get_plugin_metadata."""
        logger = MagicMock()
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        manager = PluginManager(plugins_dir=plugins_dir, logger=logger)

        plugin = ConcretePlugin()
        manager._loaded_plugins["test_plugin"] = plugin

        metadata = manager.get_plugin_metadata()

        assert len(metadata) == 1
        assert metadata[0]["id"] == "test_plugin"
        assert metadata[0]["name"] == "Test Plugin"
        assert metadata[0]["version"] == "1.0.0"

    def test_get_loaded_plugins(self, tmp_path):
        """Test get_loaded_plugins returns dict of loaded plugins."""
        logger = MagicMock()
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        manager = PluginManager(plugins_dir=plugins_dir, logger=logger)

        plugin = ConcretePlugin()
        manager._loaded_plugins["test_plugin"] = plugin

        loaded = manager.get_loaded_plugins()

        assert "test_plugin" in loaded
        assert loaded["test_plugin"] == plugin


# ============================================================================
# GitPRTool Tests
# ============================================================================


class TestGitPRTool:
    """Tests for GitPRTool class."""

    def test_pr_result_to_dict(self):
        """Test PRResult.to_dict serialization."""
        result = PRResult(
            success=True,
            pr_url="https://github.com/user/repo/pull/123",
            pr_number=123,
            error=None,
        )

        result_dict = result.to_dict()

        assert result_dict["success"] is True
        assert result_dict["pr_url"] == "https://github.com/user/repo/pull/123"
        assert result_dict["pr_number"] == 123
        assert result_dict["error"] is None

    @patch("subprocess.run")
    def test_create_pr_success(self, mock_run, tmp_path):
        """Test create_pr with mocked subprocess (success case)."""
        logger = MagicMock()
        git_manager = MagicMock()

        with patch("backend.utils.core.git_pr_tool.GitManager", return_value=git_manager):
            tool = GitPRTool(repo_path=str(tmp_path), logger=logger)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "https://github.com/user/repo/pull/123"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = tool.create_pr(
            title="Test PR",
            body="Test body",
            base="main",
            labels=["enhancement"],
            draft=False,
        )

        assert result.success is True
        assert result.pr_url == "https://github.com/user/repo/pull/123"
        assert result.pr_number == 123
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_create_pr_failure(self, mock_run, tmp_path):
        """Test create_pr with mocked subprocess (failure case)."""
        logger = MagicMock()
        git_manager = MagicMock()

        with patch("backend.utils.core.git_pr_tool.GitManager", return_value=git_manager):
            tool = GitPRTool(repo_path=str(tmp_path), logger=logger)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: authentication required"
        mock_run.return_value = mock_result

        result = tool.create_pr(title="Test PR", body="Test body")

        assert result.success is False
        assert "authentication required" in result.error

    @patch("subprocess.run")
    def test_create_pr_gh_not_found(self, mock_run, tmp_path):
        """Test create_pr when gh CLI not found (FileNotFoundError)."""
        logger = MagicMock()
        git_manager = MagicMock()

        with patch("backend.utils.core.git_pr_tool.GitManager", return_value=git_manager):
            tool = GitPRTool(repo_path=str(tmp_path), logger=logger)

        mock_run.side_effect = FileNotFoundError

        result = tool.create_pr(title="Test PR", body="Test body")

        assert result.success is False
        assert "gh CLI not installed" in result.error

    @patch("subprocess.run")
    def test_list_open_prs(self, mock_run, tmp_path):
        """Test list_open_prs with mocked subprocess."""
        logger = MagicMock()
        git_manager = MagicMock()

        with patch("backend.utils.core.git_pr_tool.GitManager", return_value=git_manager):
            tool = GitPRTool(repo_path=str(tmp_path), logger=logger)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            [
                {
                    "number": 123,
                    "title": "Test PR",
                    "url": "https://github.com/user/repo/pull/123",
                    "state": "OPEN",
                    "headRefName": "feature-branch",
                },
                {
                    "number": 124,
                    "title": "Another PR",
                    "url": "https://github.com/user/repo/pull/124",
                    "state": "OPEN",
                    "headRefName": "another-branch",
                },
            ]
        )
        mock_run.return_value = mock_result

        prs = tool.list_open_prs()

        assert len(prs) == 2
        assert prs[0]["number"] == 123
        assert prs[1]["number"] == 124

    @patch("subprocess.run")
    def test_merge_pr(self, mock_run, tmp_path):
        """Test merge_pr with mocked subprocess."""
        logger = MagicMock()
        git_manager = MagicMock()

        with patch("backend.utils.core.git_pr_tool.GitManager", return_value=git_manager):
            tool = GitPRTool(repo_path=str(tmp_path), logger=logger)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "✓ Merged Pull Request #123"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = tool.merge_pr(pr_number=123, method="squash")

        assert result["success"] is True
        assert "Merged" in result["output"]
        mock_run.assert_called_once()


# ============================================================================
# AdvancedTriggerManager Tests
# ============================================================================


class TestAdvancedTriggerManager:
    """Tests for AdvancedTriggerManager class."""

    def test_register_composite_trigger(self):
        """Test register_composite_trigger stores trigger."""
        manager = AdvancedTriggerManager()

        condition = CompositeTriggerCondition(
            id="cond1",
            operator=LogicOperator.AND,
            sub_conditions=[
                {"metric": "cpu_usage", "operator": ">", "value": 80},
                {"metric": "memory_usage", "operator": ">", "value": 70},
            ],
        )

        callback = MagicMock()
        success = manager.register_composite_trigger(
            trigger_id="trigger1",
            name="High Resource Usage",
            composite_condition=condition,
            action_callback=callback,
            cooldown_seconds=60,
            enabled=True,
        )

        assert success is True
        assert "trigger1" in manager.triggers
        assert manager.triggers["trigger1"]["name"] == "High Resource Usage"
        assert manager.triggers["trigger1"]["cooldown_seconds"] == 60
        assert manager.trigger_states["trigger1"] == TriggerState.INACTIVE

    def test_evaluate_trigger_with_and_conditions(self):
        """Test evaluate_trigger with AND conditions."""
        manager = AdvancedTriggerManager()

        # Sub-conditions without "operator" key will use _evaluate_simple_condition
        # which defaults operator to "==" but we need to check > so we need the operator field
        # The code checks for "operator" key which causes both to be treated as composite
        # So let's make them proper simple conditions by checking the actual comparison
        condition = CompositeTriggerCondition(
            id="cond1",
            operator=LogicOperator.AND,
            sub_conditions=[
                {"metric": "cpu", "value": 50},  # No operator, will default to ==
                {"metric": "memory", "value": 60},
            ],
        )

        manager.register_composite_trigger(
            trigger_id="trigger1",
            name="Test AND",
            composite_condition=condition,
        )

        # Both conditions true with exact match
        context = {"cpu": 50, "memory": 60}
        result = manager.evaluate_trigger("trigger1", context)
        assert result is True

        # One condition false
        context = {"cpu": 40, "memory": 60}
        result = manager.evaluate_trigger("trigger1", context)
        assert result is False

    def test_evaluate_trigger_with_or_conditions(self):
        """Test evaluate_trigger with OR conditions."""
        manager = AdvancedTriggerManager()

        # Simple conditions without operator key
        condition = CompositeTriggerCondition(
            id="cond1",
            operator=LogicOperator.OR,
            sub_conditions=[
                {"metric": "error_rate", "value": 5},
                {"metric": "response_time", "value": 1000},
            ],
        )

        manager.register_composite_trigger(
            trigger_id="trigger1",
            name="Test OR",
            composite_condition=condition,
        )

        # Both conditions false
        context = {"error_rate": 2, "response_time": 500}
        assert manager.evaluate_trigger("trigger1", context) is False

        # One condition true
        context = {"error_rate": 5, "response_time": 500}
        assert manager.evaluate_trigger("trigger1", context) is True

        # Both conditions true
        context = {"error_rate": 5, "response_time": 1000}
        assert manager.evaluate_trigger("trigger1", context) is True

    def test_evaluate_trigger_with_not_conditions(self):
        """Test evaluate_trigger with NOT conditions."""
        manager = AdvancedTriggerManager()

        # Simple conditions without operator key (defaults to ==)
        condition = CompositeTriggerCondition(
            id="cond1",
            operator=LogicOperator.NOT,
            sub_conditions=[
                {"metric": "is_healthy", "value": True},
            ],
        )

        manager.register_composite_trigger(
            trigger_id="trigger1",
            name="Test NOT",
            composite_condition=condition,
        )

        # Condition true -> NOT makes it false
        context = {"is_healthy": True}
        assert manager.evaluate_trigger("trigger1", context) is False

        # Condition false -> NOT makes it true
        context = {"is_healthy": False}
        assert manager.evaluate_trigger("trigger1", context) is True

    def test_fire_trigger(self):
        """Test fire_trigger updates state and history."""
        manager = AdvancedTriggerManager()

        callback = MagicMock(return_value={"action": "executed"})

        # Simple conditions without operator key
        condition = CompositeTriggerCondition(
            id="cond1",
            operator=LogicOperator.AND,
            sub_conditions=[{"metric": "test", "value": 1}],
        )

        manager.register_composite_trigger(
            trigger_id="trigger1",
            name="Test Trigger",
            composite_condition=condition,
            action_callback=callback,
        )

        context = {"test": 1}
        result = manager.fire_trigger("trigger1", context)

        assert result["success"] is True
        assert result["trigger_id"] == "trigger1"
        assert result["trigger_name"] == "Test Trigger"
        assert result["callback_result"] == {"action": "executed"}
        assert manager.triggers["trigger1"]["fire_count"] == 1
        assert manager.trigger_states["trigger1"] == TriggerState.FIRED
        callback.assert_called_once_with(context)

    def test_detect_conflicts(self):
        """Test detect_conflicts finds overlapping triggers."""
        manager = AdvancedTriggerManager()

        cond1 = CompositeTriggerCondition(
            id="cond1",
            operator=LogicOperator.AND,
            sub_conditions=[{"metric": "cpu", "operator": ">", "value": 80}],
        )

        cond2 = CompositeTriggerCondition(
            id="cond2",
            operator=LogicOperator.AND,
            sub_conditions=[{"metric": "cpu", "operator": ">", "value": 85}],
        )

        manager.register_composite_trigger(
            trigger_id="trigger1",
            name="High CPU 1",
            composite_condition=cond1,
        )

        manager.register_composite_trigger(
            trigger_id="trigger2",
            name="High CPU 2",
            composite_condition=cond2,
        )

        conflicts = manager.detect_conflicts()

        assert len(conflicts) >= 1
        assert conflicts[0]["trigger1"] == "trigger1"
        assert conflicts[0]["trigger2"] == "trigger2"
        assert conflicts[0]["conflict_type"] == "simultaneous_fire"

    def test_get_trigger_status_single(self):
        """Test get_trigger_status for single trigger."""
        manager = AdvancedTriggerManager()

        # Simple conditions without operator key
        condition = CompositeTriggerCondition(
            id="cond1",
            operator=LogicOperator.AND,
            sub_conditions=[{"metric": "test", "value": 1}],
        )

        manager.register_composite_trigger(
            trigger_id="trigger1",
            name="Test Trigger",
            composite_condition=condition,
        )

        status = manager.get_trigger_status("trigger1")

        assert status["id"] == "trigger1"
        assert status["name"] == "Test Trigger"
        assert status["state"] == TriggerState.INACTIVE.value
        assert status["enabled"] is True
        assert status["fire_count"] == 0
        assert status["last_fired"] is None

    def test_get_trigger_status_all(self):
        """Test get_trigger_status for all triggers."""
        manager = AdvancedTriggerManager()

        # Simple conditions without operator key
        cond1 = CompositeTriggerCondition(
            id="cond1",
            operator=LogicOperator.AND,
            sub_conditions=[{"metric": "test", "value": 1}],
        )

        cond2 = CompositeTriggerCondition(
            id="cond2",
            operator=LogicOperator.OR,
            sub_conditions=[{"metric": "test", "value": 2}],
        )

        manager.register_composite_trigger(
            trigger_id="trigger1",
            name="Test 1",
            composite_condition=cond1,
        )

        manager.register_composite_trigger(
            trigger_id="trigger2",
            name="Test 2",
            composite_condition=cond2,
        )

        status = manager.get_trigger_status()

        assert "trigger1" in status
        assert "trigger2" in status
        assert status["trigger1"]["name"] == "Test 1"
        assert status["trigger2"]["name"] == "Test 2"

    def test_cooldown_mechanism(self):
        """Test cooldown mechanism."""
        manager = AdvancedTriggerManager()

        # Simple conditions without operator key
        condition = CompositeTriggerCondition(
            id="cond1",
            operator=LogicOperator.AND,
            sub_conditions=[{"metric": "test", "value": 1}],
        )

        manager.register_composite_trigger(
            trigger_id="trigger1",
            name="Cooldown Test",
            composite_condition=condition,
            cooldown_seconds=3600,  # 1 hour
        )

        context = {"test": 1}

        # Fire trigger
        manager.fire_trigger("trigger1", context)

        # Check that it's in cooldown
        assert manager.trigger_states["trigger1"] == TriggerState.COOLDOWN

        # Evaluate should return False due to cooldown
        assert manager.evaluate_trigger("trigger1", context) is False

    def test_dependency_checking(self):
        """Test dependency checking."""
        manager = AdvancedTriggerManager()

        # Simple conditions without operator key
        cond1 = CompositeTriggerCondition(
            id="cond1",
            operator=LogicOperator.AND,
            sub_conditions=[{"metric": "test", "value": 1}],
        )

        cond2 = CompositeTriggerCondition(
            id="cond2",
            operator=LogicOperator.AND,
            sub_conditions=[{"metric": "test", "value": 2}],
        )

        manager.register_composite_trigger(
            trigger_id="required_trigger",
            name="Required",
            composite_condition=cond1,
        )

        manager.register_composite_trigger(
            trigger_id="dependent_trigger",
            name="Dependent",
            composite_condition=cond2,
        )

        # Add dependency
        success = manager.add_trigger_dependency(
            dependent_trigger_id="dependent_trigger",
            required_trigger_id="required_trigger",
            condition="must_have_fired",
        )

        assert success is True

        # Dependent trigger should not evaluate before required trigger fires
        context = {"test": 2}
        assert manager.evaluate_trigger("dependent_trigger", context) is False

        # Fire required trigger
        context1 = {"test": 1}
        manager.fire_trigger("required_trigger", context1)

        # Now dependent trigger should evaluate
        context2 = {"test": 2}
        assert manager.evaluate_trigger("dependent_trigger", context2) is True
