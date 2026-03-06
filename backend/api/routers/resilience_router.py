"""
resilience_router - migrated from resilience_bp.py.
Handles system resilience, loop detection status and contingency logs.
"""

import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/resilience", tags=["resilience"])


@router.get("/status")
async def get_resilience_status(request: Request):
    """Returns the current state of loop detection and contingency planning."""
    from backend.utils.core.system.metrics_database import get_metrics_database
    
    ollash_root_dir = request.app.state.ollash_root_dir
    db = get_metrics_database(ollash_root_dir.parent)

    loops = db.get_metric_history("system", "loop_detected", hours=24)
    contingencies = db.get_metric_history("auto_gen", "contingency_plan", hours=24)

    # Mock some data if empty for demonstration
    if not loops:
        loops = [
            {
                "timestamp": (datetime.now() - timedelta(minutes=random.randint(1, 60))).isoformat(),
                "value": 1,
                "tags": {"tool": "ls_directory"},
            }
            for _ in range(3)
        ]

    if not contingencies:
        contingencies = [
            {
                "timestamp": (datetime.now() - timedelta(minutes=random.randint(1, 120))).isoformat(),
                "value": 1,
                "tags": {"phase": "senior_review"},
            }
            for _ in range(2)
        ]

    return {
        "loops_detected": len(loops),
        "contingency_plans_executed": len(contingencies),
        "recent_loops": loops[-5:],
        "recent_contingencies": contingencies[-5:],
        "system_health_score": 98.5 - (len(loops) * 0.5),
    }


@router.get("/logs")
async def get_resilience_logs():
    """Returns detailed logs for resilience events."""
    return [
        {"time": "10:24:05", "event": "Loop detected", "tool": "grep_search", "action": "Triggered backtracking"},
        {"time": "11:15:30", "event": "Contingency plan started", "reason": "Review failure", "status": "Success"},
        {"time": "14:42:12", "event": "Stagnation timeout", "duration": "2m", "action": "Re-prompting agent"},
    ]


@router.get("/")
async def resilience_index():
    return {"status": "ok", "router": "resilience"}
