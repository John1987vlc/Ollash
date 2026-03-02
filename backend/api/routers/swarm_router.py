"""
swarm_router — migrated from swarm_bp.py.
TODO: Migrate route logic from frontend/blueprints/swarm_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/swarm", tags=["swarm"])


@router.get("/")
async def swarm_index():
    """Index endpoint — implement from swarm_bp.py."""
    return {"status": "ok", "router": "swarm"}
