"""Swarm router — domain agent swarm operations via CoworkTools."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/swarm", tags=["swarm"])


class SwarmTaskRequest(BaseModel):
    task: str
    doc_name: str | None = None


@router.get("/")
async def swarm_index():
    return {"status": "ok", "endpoints": ["/doc-to-task", "/log-audit", "/summary"]}


def _get_cowork_tools():
    """Instantiate CoworkTools with the container's LLM client."""
    from backend.core.containers import main_container
    from backend.utils.domains.bonus.cowork_impl import CoworkTools
    from backend.utils.core.io.documentation_manager import DocumentationManager
    from backend.utils.core.system.structured_logger import StructuredLogger
    from backend.utils.core.system.agent_logger import AgentLogger

    root = Path(".")
    log_path = root / ".ollash" / "swarm.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    sl = StructuredLogger(log_path, "swarm")
    al = AgentLogger(sl, "SwarmAPI")
    llm_client = main_container.auto_agent_module.llm_client_manager().get_client("generalist")
    doc_manager = DocumentationManager(root, al, None, {})
    workspace = root / ".ollash" / "knowledge_workspace"
    return CoworkTools(doc_manager, llm_client, al, workspace)


@router.post("/doc-to-task")
async def doc_to_task(req: SwarmTaskRequest):
    """Convert a document into actionable tasks using the swarm."""
    try:
        tools = _get_cowork_tools()
        doc_name = req.doc_name or req.task.split()[-1]
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, tools.document_to_task, doc_name)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/log-audit")
async def log_audit(req: SwarmTaskRequest):
    """Audit recent logs using the AuditorAgent."""
    try:
        tools = _get_cowork_tools()
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, tools.analyze_recent_logs)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summary")
async def swarm_summary(req: SwarmTaskRequest):
    """Generate an executive summary of a document."""
    try:
        tools = _get_cowork_tools()
        doc_name = req.doc_name or req.task.split()[-1]
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, tools.generate_executive_summary, doc_name)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def swarm_status():
    """Return the current swarm status (running agents, tasks)."""
    try:
        from backend.core.containers import main_container

        orchestrator = main_container.domain_agents.domain_agent_orchestrator()
        status = getattr(orchestrator, "get_status", lambda: {"running": False})()
        return {"status": "ok", "swarm": status}
    except Exception as e:
        return {"status": "unavailable", "detail": str(e)}
