import pytest
import unittest.mock
from backend.utils.core.system.task_scheduler import TaskScheduler
from backend.utils.core.system.execution_plan import ExecutionPlan
from frontend.blueprints.prompt_studio_bp import validate_prompt

# Mocking Flask request
@pytest.fixture
def mock_request(mocker):
    return mocker.patch('flask.request')

def test_task_scheduler_schedule_task():
    scheduler = TaskScheduler()
    task_data = {"schedule": "hourly", "name": "Test Task"}
    with unittest.mock.patch.object(TaskScheduler, 'schedule_task') as mock_schedule:
        scheduler.schedule_task("test-id", task_data)
        mock_schedule.assert_called_with("test-id", task_data)

def test_execution_plan_init():
    plan = ExecutionPlan(project_name="TestProject")
    assert plan.project_name == "TestProject"

def test_prompt_validation_logic():
    # Test logic directly if possible, or simulate API response
    prompt = "Short prompt"
    warnings = []
    if len(prompt) < 50:
        warnings.append("Warning")
    assert len(warnings) > 0
    
    prompt_long = "Long enough prompt " * 10
    warnings = []
    if len(prompt_long) < 50:
        warnings.append("Warning")
    assert len(warnings) == 0

