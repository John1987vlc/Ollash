"""
automations_router - migrated from automations_bp.py.
Handles task automation scheduling.
"""

from typing import Any, Dict, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/automations", tags=["automations"])


class AutomationCreate(BaseModel):
    name: str
    agent: str
    prompt: str
    schedule: Dict[str, Any]
    notifyEmail: Optional[bool] = False
    meta: Optional[Dict[str, Any]] = {}


class AutomationUpdate(BaseModel):
    enabled: Optional[bool] = None
    name: Optional[str] = None
    agent: Optional[str] = None
    prompt: Optional[str] = None
    schedule: Optional[Dict[str, Any]] = None
    notifyEmail: Optional[bool] = None


@router.get("/")
async def get_automations(request: Request):
    """Fetch all scheduled tasks."""
    am = request.app.state.automation_manager
    return am.get_tasks()


@router.post("/")
async def create_automation(payload: AutomationCreate, request: Request):
    """Create a new scheduled task."""
    am = request.app.state.automation_manager

    task_id = f"task_{int(datetime.now().timestamp() * 1000)}"

    task_data = {
        "task_id": task_id,
        "name": payload.name,
        "agent": payload.agent,
        "prompt": payload.prompt,
        "schedule": payload.schedule,
        "notifyEmail": payload.notifyEmail,
        "meta": payload.meta,
        "enabled": True,
        "createdAt": datetime.now().isoformat(),
    }

    # Add to manager and schedule
    am.tasks[task_id] = task_data
    am._schedule_task(task_id, task_data)
    am._save_tasks()

    return {"status": "created", "id": task_id, "task": task_data}


@router.delete("/{task_id}")
async def delete_automation(task_id: str, request: Request):
    """Delete a scheduled task."""
    am = request.app.state.automation_manager
    if task_id not in am.tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    # Unschedule
    if am.scheduler.get_job(task_id):
        am.scheduler.remove_job(task_id)

    del am.tasks[task_id]
    am._save_tasks()

    return {"status": "deleted"}


@router.put("/{task_id}/toggle")
async def toggle_automation(task_id: str, request: Request):
    """Enable/disable a scheduled task."""
    am = request.app.state.automation_manager
    if task_id not in am.tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = am.tasks[task_id]
    task["enabled"] = not task.get("enabled", True)

    # Update scheduler
    if task["enabled"]:
        am._schedule_task(task_id, task)
    else:
        if am.scheduler.get_job(task_id):
            am.scheduler.remove_job(task_id)

    am._save_tasks()

    return {"id": task_id, "enabled": task["enabled"]}


@router.post("/{task_id}/run")
async def run_automation_now(task_id: str, request: Request):
    """Run a scheduled task immediately."""
    am = request.app.state.automation_manager
    if task_id not in am.tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = am.tasks[task_id]

    # Execute in background thread via manager's helper
    import asyncio

    asyncio.create_task(am._execute_task_wrapper(task_id, task))

    return {"status": "executing", "message": f"Task '{task['name']}' started"}
