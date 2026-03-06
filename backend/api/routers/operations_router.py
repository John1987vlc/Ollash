"""
operations_router - migrated from operations_views.py.
Handles task scheduling and execution plan (DAG) previews.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/operations", tags=["operations"])

# In-memory mock storage for demonstration (kept from operations_views.py)
scheduler_jobs = [
    {
        "id": "job_1",
        "name": "Daily System Backup",
        "cron": "0 0 * * *",
        "next_run": (datetime.now() + timedelta(days=1)).isoformat(),
        "status": "active",
    },
    {
        "id": "job_2",
        "name": "Weekly Model Retraining",
        "cron": "0 2 * * 0",
        "next_run": (datetime.now() + timedelta(days=3)).isoformat(),
        "status": "paused",
    },
]


class JobCreateRequest(BaseModel):
    name: str
    cron: str


class DagPreviewRequest(BaseModel):
    task: str


@router.get("/api/jobs")
async def get_jobs():
    """Returns all scheduled jobs."""
    return scheduler_jobs


@router.post("/api/jobs")
async def create_job(payload: JobCreateRequest):
    """Creates a new scheduled job."""
    new_job = {
        "id": f"job_{uuid.uuid4().hex[:8]}",
        "name": payload.name,
        "cron": payload.cron,
        "next_run": (datetime.now() + timedelta(days=1)).isoformat(),
        "status": "active",
    }
    scheduler_jobs.append(new_job)
    return new_job


@router.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Deletes a scheduled job."""
    global scheduler_jobs
    scheduler_jobs = [job for job in scheduler_jobs if job["id"] != job_id]
    return {"status": "success"}


@router.post("/api/dag/preview")
async def preview_dag(payload: DagPreviewRequest):
    """Generates a visual execution plan (DAG) for a complex task."""
    # Mock DAG generation
    dag = {
        "nodes": [
            {"id": "1", "label": "Analyze Requirements", "type": "thinking"},
            {"id": "2", "label": "Search Codebase", "type": "tool"},
            {"id": "3", "label": "Plan Architecture", "type": "thinking"},
            {"id": "4", "label": "Write Code", "type": "action"},
            {"id": "5", "label": "Run Tests", "type": "validation"},
        ],
        "edges": [
            {"from": "1", "to": "2"},
            {"from": "2", "to": "3"},
            {"from": "3", "to": "4"},
            {"from": "4", "to": "5"},
        ],
    }
    return dag


@router.get("/")
async def operations_index():
    return {"status": "ok", "router": "operations"}
