"""
metrics_router — migrated from metrics_bp.py.
TODO: Migrate route logic from frontend/blueprints/metrics_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/")
async def metrics_index():
    """Index endpoint — implement from metrics_bp.py."""
    return {"status": "ok", "router": "metrics"}
