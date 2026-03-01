"""Unit tests for AutomationManager execution history (E6)."""

import pytest
from unittest.mock import MagicMock, patch

from backend.utils.core.system.task_models import ExecutionRecord


@pytest.mark.unit
class TestAutomationManagerExecutionHistory:
    """Tests for AutomationManager.record_execution and get_last_execution_summary."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create an AutomationManager backed by a temp directory."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        tasks_file = config_dir / "tasks.json"
        tasks_file.write_text(
            '{"tasks": [{"task_id": "t1", "name": "Task One", "enabled": true, "schedule": {"type": "interval", "interval_minutes": 60}}]}'
        )

        mock_event_publisher = MagicMock()
        mock_logger = MagicMock()

        # Patch AgentKernel to avoid side effects
        with patch("backend.utils.core.system.automation_manager.BackgroundScheduler"):
            from backend.utils.core.system.automation_manager import AutomationManager

            mgr = AutomationManager(
                ollash_root_dir=tmp_path,
                event_publisher=mock_event_publisher,
                agent_logger=mock_logger,
            )
        return mgr

    def test_record_execution_appends_to_history(self, manager):
        record = ExecutionRecord(status="success", summary="done", duration_seconds=1.5)
        manager.record_execution("t1", record)

        task = manager.tasks["t1"]
        assert len(task["execution_history"]) == 1
        assert task["execution_history"][0]["status"] == "success"
        assert task["execution_history"][0]["summary"] == "done"

    def test_record_execution_updates_last_success(self, manager):
        record = ExecutionRecord(status="success", summary="ok")
        manager.record_execution("t1", record)

        assert manager.tasks["t1"]["last_success"] is not None

    def test_record_execution_updates_last_error(self, manager):
        record = ExecutionRecord(status="error", errors=["Something broke"])
        manager.record_execution("t1", record)

        assert manager.tasks["t1"]["last_error"] is not None

    def test_record_execution_trims_to_max_history(self, manager):
        for i in range(55):
            manager.record_execution("t1", ExecutionRecord(status="success", summary=f"run {i}"))

        assert len(manager.tasks["t1"]["execution_history"]) == manager.MAX_HISTORY_PER_TASK

    def test_record_execution_keeps_most_recent_on_trim(self, manager):
        for i in range(55):
            manager.record_execution("t1", ExecutionRecord(status="success", summary=f"run {i}"))

        history = manager.tasks["t1"]["execution_history"]
        # Last entry should be run 54
        assert history[-1]["summary"] == "run 54"

    def test_get_last_execution_summary_returns_most_recent(self, manager):
        manager.record_execution("t1", ExecutionRecord(status="success", summary="first"))
        manager.record_execution("t1", ExecutionRecord(status="error", summary="second", errors=["oops"]))

        result = manager.get_last_execution_summary("t1")

        assert result is not None
        assert result.status == "error"
        assert result.summary == "second"

    def test_get_last_execution_summary_returns_none_for_unknown_task(self, manager):
        result = manager.get_last_execution_summary("nonexistent_task_id")

        assert result is None

    def test_get_last_execution_summary_returns_none_when_no_history(self, manager):
        result = manager.get_last_execution_summary("t1")

        assert result is None

    def test_record_execution_ignores_unknown_task_id(self, manager):
        # Should not raise
        manager.record_execution("unknown_id", ExecutionRecord(status="success"))
        assert "unknown_id" not in manager.tasks
