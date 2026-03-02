"""
project_graph_router — migrated from project_graph_bp.py.
TODO: Migrate route logic from frontend/blueprints/project_graph_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/project-graph", tags=["project-graph"])


@router.get("/")
async def project_graph_index():
    """Index endpoint — implement from project_graph_bp.py."""
    return {"status": "ok", "router": "project-graph"}
