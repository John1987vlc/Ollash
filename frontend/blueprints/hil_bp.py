"""
Human-in-the-Loop (HITL) Blueprint — P1 extension.

Original endpoints kept; new integration with ActiveOrchestrators so that
POST /api/hil/respond can unblock a live DAG node, not just fire a bare event.

GET  /api/hil/pending        List all pending HITL requests (from DAG + legacy store).
POST /api/hil/respond        Submit an answer; unblocks the matching DAG node.
POST /api/hil/debug/add      Dev helper to inject a fake request.
"""

from __future__ import annotations

import datetime
import uuid

from flask import Blueprint, jsonify, request

hil_bp = Blueprint("hil", __name__)

# In-memory store for legacy / debug requests
_pending_requests: dict = {}


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
# GET /api/hil/pending
# ---------------------------------------------------------------------------

@hil_bp.route("/api/hil/pending", methods=["GET"])
def get_pending():
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

    return jsonify(sorted(requests_list, key=lambda x: x["timestamp"], reverse=True))


# ---------------------------------------------------------------------------
# POST /api/hil/respond
# ---------------------------------------------------------------------------

@hil_bp.route("/api/hil/respond", methods=["POST"])
def respond_hil():
    """Submit a response to a HITL request.

    JSON body:
        request_id  — task node ID (or legacy request ID)
        response    — "approve" | "reject" | free-text answer
        feedback    — optional extra text
    """
    data = request.json or {}
    request_id: str = data.get("request_id", "")
    response: str = data.get("response", "")
    feedback: str = data.get("feedback", "")
    answer: str = feedback or response

    if not request_id or not response:
        return jsonify({"error": "Missing request_id or response"}), 400

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
                        asyncio.run_coroutine_threadsafe(
                            dag.mark_unblocked(request_id, answer), loop
                        )
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

    # Publish event regardless (existing subscribers may handle it)
    try:
        from backend.utils.core.system.event_publisher import EventPublisher
        EventPublisher().publish(
            "hil_response",
            request_id=request_id,
            response=response,
            feedback=feedback,
        )
    except Exception:
        pass

    return jsonify({"status": "success", "unblocked_dag_node": unblocked})


# ---------------------------------------------------------------------------
# POST /api/hil/debug/add  (dev helper)
# ---------------------------------------------------------------------------

@hil_bp.route("/api/hil/debug/add", methods=["POST"])
def add_debug_request():
    data = request.json or {}
    req_id = str(uuid.uuid4())[:8]
    _pending_requests[req_id] = {
        "type": data.get("type", "write_file"),
        "title": data.get("title", "Modificar archivo"),
        "details": data.get("details", {}),
        "timestamp": datetime.datetime.now().isoformat(),
        "agent": data.get("agent", "AutoAgent"),
        "project": data.get("project", ""),
    }
    return jsonify({"id": req_id})
