"""
knowledge_graph_router — migrated from knowledge_graph_bp.py.
TODO: Migrate route logic from frontend/blueprints/knowledge_graph_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/knowledge-graph", tags=["knowledge-graph"])


@router.get("/")
async def knowledge_graph_index():
    """Index endpoint — implement from knowledge_graph_bp.py."""
    return {"status": "ok", "router": "knowledge-graph"}
