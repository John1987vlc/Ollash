"""
benchmark_router - migrated from benchmark_bp.py.
TODO: Migrate route logic from frontend/blueprints/benchmark_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/benchmark", tags=["benchmark"])


@router.get("/")
async def benchmark_index():
    """Index endpoint - implement from benchmark_bp.py."""
    return {"status": "ok", "router": "benchmark"}
