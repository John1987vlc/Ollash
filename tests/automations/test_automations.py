"""Tests for automation system"""

import pytest
import json
from pathlib import Path
from datetime import datetime


def test_notification_manager_initialization(tmp_path):
    """Test that NotificationManager initializes correctly"""
    from src.utils.core.notification_manager import NotificationManager
    
    nm = NotificationManager()
    assert nm is not None
    assert isinstance(nm.subscribed_emails, set)


def test_notification_manager_email_subscription(tmp_path):
    """Test email subscription functionality"""
    from src.utils.core.notification_manager import NotificationManager
    
    nm = NotificationManager()
    
    # Valid email
    assert nm.subscribe_email('test@example.com') == True
    assert 'test@example.com' in nm.subscribed_emails
    
    # Invalid email
    assert nm.subscribe_email('invalid-email') == False
    
    # Unsubscribe
    assert nm.unsubscribe_email('test@example.com') == True
    assert 'test@example.com' not in nm.subscribed_emails


def test_task_scheduler_initialization():
    """Test TaskScheduler initialization"""
    from src.utils.core.task_scheduler import TaskScheduler
    
    scheduler = TaskScheduler()
    assert scheduler is not None
    scheduler.initialize()
    assert scheduler.scheduler is not None


def test_task_scheduler_trigger_creation():
    """Test trigger creation for different schedule types"""
    from src.utils.core.task_scheduler import TaskScheduler
    
    scheduler = TaskScheduler()
    
    # Test hourly trigger
    data = {'schedule': 'hourly'}
    trigger = scheduler._get_trigger(data)
    assert trigger is not None
    
    # Test daily trigger
    data = {'schedule': 'daily'}
    trigger = scheduler._get_trigger(data)
    assert trigger is not None
    
    # Test weekly trigger
    data = {'schedule': 'weekly'}
    trigger = scheduler._get_trigger(data)
    assert trigger is not None
    
    # Test custom cron trigger
    data = {'schedule': 'custom', 'cron': '0 8 * * *'}
    trigger = scheduler._get_trigger(data)
    assert trigger is not None


def test_automation_executor_initialization(tmp_path):
    """Test AutomationTaskExecutor initialization"""
    from src.utils.core.automation_executor import AutomationTaskExecutor
    from src.utils.core.event_publisher import EventPublisher
    
    ollash_root = tmp_path / "ollash"
    ollash_root.mkdir()
    
    event_pub = EventPublisher()
    executor = AutomationTaskExecutor(ollash_root, event_pub)
    
    assert executor is not None
    assert executor.ollash_root_dir == ollash_root
    assert executor.notification_manager is not None


def test_automations_bp_storage(tmp_path):
    """Test automations blueprint storage functionality"""
    import src.web.blueprints.automations_bp as auto_bp
    
    # Mock storage file
    storage_file = tmp_path / "scheduled_tasks.json"
    auto_bp._tasks_storage_file = storage_file
    auto_bp._scheduled_tasks = {}
    
    # Save empty tasks
    auto_bp.save_tasks_to_storage()
    assert storage_file.exists()
    
    # Add a task
    task_data = {
        "name": "Test Task",
        "agent": "system",
        "prompt": "Test prompt",
        "schedule": "hourly",
        "status": "active"
    }
    auto_bp._scheduled_tasks["task_123"] = task_data
    auto_bp.save_tasks_to_storage()
    
    # Load and verify
    auto_bp._scheduled_tasks = {}
    auto_bp.load_tasks_from_storage()
    
    assert "task_123" in auto_bp._scheduled_tasks
    assert auto_bp._scheduled_tasks["task_123"]["name"] == "Test Task"


def test_html_email_building():
    """Test HTML email generation"""
    from src.utils.core.notification_manager import NotificationManager
    
    nm = NotificationManager()
    html = nm._build_html_email(
        title="Test Title",
        content="<p>Test content</p>",
        status="success"
    )
    
    assert "<!DOCTYPE html>" in html
    assert "Test Title" in html
    assert "Test content" in html
    assert "#10b981" in html  # success color


@pytest.mark.asyncio
async def test_automation_executor_task_execution(tmp_path):
    """Test task execution (without actual agent)"""
    from src.utils.core.automation_executor import AutomationTaskExecutor
    from src.utils.core.event_publisher import EventPublisher
    
    ollash_root = tmp_path / "ollash"
    ollash_root.mkdir()
    
    event_pub = EventPublisher()
    executor = AutomationTaskExecutor(ollash_root, event_pub)
    
    # Mock task data - this will fail because no actual agent
    task_data = {
        'name': 'Test Task',
        'agent': 'orchestrator',
        'prompt': 'Test prompt'
    }
    
    # We expect this to fail gracefully
    result = await executor.execute_task('test_123', task_data)
    
    assert result['task_id'] == 'test_123'
    assert result['task_name'] == 'Test Task'
    # Status might be error since we don't have a real Ollash setup


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
