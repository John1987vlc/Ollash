"""Health check router — migrated from system_health_bp.py."""

import random
from fastapi import APIRouter

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/")
async def get_system_health():
    """System health status."""
    return {
        "status": "ok",
        "cpu": random.randint(10, 40),
        "ram": random.randint(30, 60),
        "models": [
            {"name": "qwen3-coder:30b", "status": "online", "latency": 120},
        ],
    }
