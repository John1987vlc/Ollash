"""Tests for automation system"""

from unittest.mock import MagicMock

import pytest

# Import functions directly from the module under test


def test_notification_manager_initialization(tmp_path):
    """Test that NotificationManager initializes correctly"""
    from backend.utils.core.notification_manager import NotificationManager

    nm = NotificationManager()
    assert nm is not None
    assert isinstance(nm.subscribed_emails, set)


def test_notification_manager_email_subscription(tmp_path):
    """Test email subscription functionality"""
    from backend.utils.core.notification_manager import NotificationManager

    nm = NotificationManager()

    # Valid email
    assert nm.subscribe_email("test@example.com") == True
    assert "test@example.com" in nm.subscribed_emails

    # Invalid email
    assert nm.subscribe_email("invalid-email") == False

    # Unsubscribe
    assert nm.unsubscribe_email("test@example.com") == True
    assert "test@example.com" not in nm.subscribed_emails


def test_task_scheduler_initialization():
    """Test TaskScheduler initialization"""
    from backend.utils.core.task_scheduler import TaskScheduler

    scheduler = TaskScheduler()
    assert scheduler is not None
    scheduler.initialize()
    assert scheduler.scheduler is not None


def test_task_scheduler_trigger_creation():
    """Test trigger creation for different schedule types"""
    from backend.utils.core.task_scheduler import TaskScheduler

    scheduler = TaskScheduler()

    # Test hourly trigger
    data = {"schedule": "hourly"}
    trigger = scheduler._get_trigger(data)
    assert trigger is not None

    # Test daily trigger
    data = {"schedule": "daily"}
    trigger = scheduler._get_trigger(data)
    assert trigger is not None

    # Test weekly trigger
    data = {"schedule": "weekly"}
    trigger = scheduler._get_trigger(data)
    assert trigger is not None

    # Test custom cron trigger
    data = {"schedule": "custom", "cron": "0 8 * * *"}
    trigger = scheduler._get_trigger(data)
    assert trigger is not None


def test_automation_executor_initialization(tmp_path):
    """Test AutomationTaskExecutor initialization"""
    from backend.utils.core.automation_executor import AutomationTaskExecutor
    from backend.utils.core.event_publisher import EventPublisher

    ollash_root = tmp_path / "ollash"
    ollash_root.mkdir()

    event_pub = EventPublisher()
    executor = AutomationTaskExecutor(ollash_root, event_pub)

    assert executor is not None
    assert executor.ollash_root_dir == ollash_root
    assert executor.notification_manager is not None


class MockPath:
    """A mock Path class to simulate path operations for testing without subclassing Path."""

    def __init__(self, path_str):
        self._path_str = str(path_str) if path_str else "."
        self._exists = False
        self._mkdir_called = False

    def __str__(self):
        return self._path_str

    def __repr__(self):
        return f"MockPath('{self._path_str}')"

    def __truediv__(self, other):
        # Create a new MockPath for the result of the division
        new_path = MockPath(f"{self._path_str}/{other}")
        new_path._exists = self._exists
        return new_path

    def exists(self):
        return self._exists

    def mkdir(self, parents=False, exist_ok=False):
        self._mkdir_called = True

    @property
    def parent(self):
        # Return a mock parent that can call mkdir
        parent_mock = MagicMock()
        parent_mock.mkdir.return_value = None
        return parent_mock


def test_html_email_building():
    """Test HTML email generation"""
    from backend.utils.core.notification_manager import NotificationManager

    nm = NotificationManager()
    html = nm._build_html_email(
        title="Test Title", content="<p>Test content</p>", status="success"
    )

    assert "<!DOCTYPE html>" in html
    assert "Test Title" in html
    assert "Test content" in html
    assert "#10b981" in html  # success color


@pytest.mark.asyncio
async def test_automation_executor_task_execution(tmp_path):
    """Test task execution (without actual agent)"""
    from backend.utils.core.automation_executor import AutomationTaskExecutor
    from backend.utils.core.event_publisher import EventPublisher

    ollash_root = tmp_path / "ollash"
    ollash_root.mkdir()

    event_pub = EventPublisher()
    executor = AutomationTaskExecutor(ollash_root, event_pub)

    # Mock task data - this will fail because no actual agent
    task_data = {"name": "Test Task", "agent": "orchestrator", "prompt": "Test prompt"}

    # We expect this to fail gracefully
    result = await executor.execute_task("test_123", task_data)

    assert result["task_id"] == "test_123"
    assert result["task_name"] == "Test Task"
    # Status might be error since we don't have a real Ollash setup


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
