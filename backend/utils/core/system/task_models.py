"""
Pydantic models for AutomationManager task configuration and execution history.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ExecutionRecord(BaseModel):
    """Records a single task execution outcome."""

    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    status: str  # "success" | "error" | "skipped"
    summary: str = ""
    errors: List[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
    files_modified: int = 0


class TaskSchedule(BaseModel):
    """Schedule configuration for a task."""

    type: str = "interval"  # "cron" | "interval"
    cron_expression: Optional[str] = None
    interval_minutes: int = 60
    human_readable: str = ""


class TaskConfig(BaseModel):
    """Full task configuration including execution history."""

    task_id: str
    name: str
    enabled: bool = True
    schedule: Dict[str, Any] = Field(default_factory=dict)
    check_tool: Optional[str] = None
    check_params: Dict[str, Any] = Field(default_factory=dict)
    execution_history: List[ExecutionRecord] = Field(default_factory=list)
    last_success: Optional[str] = None
    last_error: Optional[str] = None
