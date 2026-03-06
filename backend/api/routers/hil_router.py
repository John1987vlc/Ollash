"""
hil_router - migrated from hil_bp.py.
Handles Human-in-the-Loop (HITL) requests.
"""

import datetime
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/hil", tags=["hil"])

# In-memory store for legacy / debug requests
_pending_requests: Dict[str, Dict[str, Any]] = {}


class HILResponse(BaseModel):
    request_id: str
    response: str
    feedback: Optional[str] = None


class HILEditTask(BaseModel):
    instruction: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_active_orchestrators():
    """Return the ActiveOrchestrators singleton if available."""
    try:
        from backend.agents.orchestrators.active_orchestrators import ActiveOrchestrators

        return ActiveOrchestrators()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/pending")
async def get_pending():
    """Returns all pending HITL requests — from live DAGs plus the legacy store."""
    requests_list = []

    # Pull from live DAGs via ActiveOrchestrators
    ao = _get_active_orchestrators()
    if ao is not None:
        try:
            for project_name, orch in ao.list_active().items():
                dag = getattr(orch, "_current_dag", None)
                if dag is None and hasattr(orch, "get_dag"):
                    dag = orch.get_dag()
                if dag is None:
                    continue
                for node in dag.get_waiting_nodes():
                    requests_list.append(
                        {
                            "id": node.id,
                            "task_id": node.id,
                            "project": project_name,
                            "agent_type": str(node.agent_type),
                            "question": node.hitl_question or "Approval required",
                            "timestamp": datetime.datetime.now().isoformat(),
                            "source": "dag",
                        }
                    )
        except Exception:
            pass

    # Legacy in-memory store
    for req_id, req in _pending_requests.items():
        requests_list.append(
            {
                "id": req_id,
                "task_id": req_id,
                "project": req.get("project", ""),
                "agent_type": req.get("agent", "DefaultAgent"),
                "question": req.get("title", "Approval required"),
                "timestamp": req.get("timestamp"),
                "source": "legacy",
            }
        )

    return sorted(requests_list, key=lambda x: x["timestamp"], reverse=True)


@router.post("/respond")
async def respond_hil(payload: HILResponse, request: Request):
    """Submit a response to a HITL request."""
    request_id = payload.request_id
    response = payload.response
    feedback = payload.feedback
    answer = feedback or response

    unblocked = False

    # Try to unblock via live DAG
    ao = _get_active_orchestrators()
    if ao is not None:
        try:
            for _project, orch in ao.list_active().items():
                dag = getattr(orch, "_current_dag", None)
                if dag is None and hasattr(orch, "get_dag"):
                    dag = orch.get_dag()
                if dag is None:
                    continue
                node = dag.get_node(request_id)
                if node is not None:
                    import asyncio

                    loop = getattr(orch, "_loop", None)
                    if loop and loop.is_running():
                        asyncio.run_coroutine_threadsafe(dag.mark_unblocked(request_id, answer), loop)
                    else:
                        # Best-effort synchronous fallback
                        from backend.agents.orchestrators.task_dag import TaskStatus

                        node.hitl_answer = answer
                        node.status = TaskStatus.PENDING
                    unblocked = True
                    break
        except Exception:
            pass

    # Remove from legacy store if present
    if request_id in _pending_requests:
        _pending_requests[request_id]["status"] = response
        _pending_requests[request_id]["feedback"] = feedback
        del _pending_requests[request_id]
        unblocked = True

    # Publish event regardless
    try:
        event_publisher = request.app.state.event_publisher
        await event_publisher.publish(
            "hil_response",
            {"request_id": request_id, "response": response, "feedback": feedback},
        )
    except Exception:
        pass

    return {"status": "success", "unblocked_dag_node": unblocked}


@router.put("/edit-task/{task_id}")
async def edit_task(task_id: str, payload: HILEditTask):
    """Update the instruction of a PENDING DAG task node."""
    new_instruction = payload.instruction.strip()
    if not new_instruction:
        raise HTTPException(status_code=400, detail="Missing or empty instruction field")

    ao = _get_active_orchestrators()
    if ao is None:
        raise HTTPException(status_code=404, detail="No active orchestrators found")

    try:
        from backend.agents.orchestrators.task_dag import TaskStatus

        for project_name, orch in ao.list_active().items():
            dag = getattr(orch, "_current_dag", None)
            if dag is None and hasattr(orch, "get_dag"):
                dag = orch.get_dag()
            if dag is None:
                continue
            node = dag.get_node(task_id)
            if node is not None:
                if node.status != TaskStatus.PENDING:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Node '{task_id}' is not PENDING (current status: {node.status.value})",
                    )
                node.task_data["instruction"] = new_instruction
                return {"status": "updated", "task_id": task_id, "project": project_name}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found in any active DAG")


@router.post("/debug/add")
async def add_debug_request(data: Dict[str, Any]):
    req_id = str(uuid.uuid4())[:8]
    _pending_requests[req_id] = {
        "type": data.get("type", "write_file"),
        "title": data.get("title", "Modificar archivo"),
        "details": data.get("details", {}),
        "timestamp": datetime.datetime.now().isoformat(),
        "agent": data.get("agent", "AutoAgent"),
        "project": data.get("project", ""),
    }
    return {"id": req_id}


@router.get("/")
async def hil_index():
    return {"status": "ok", "router": "hil"}
