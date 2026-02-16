"""Blueprint for DefaultAgent interactive chat routes."""

from pathlib import Path

from flask import Blueprint, Response, jsonify, request, stream_with_context

from frontend.middleware import rate_limit_chat, require_api_key
from frontend.services.chat_session_manager import ChatSessionManager

chat_bp = Blueprint("chat", __name__)

# Initialized lazily via init_app()
_session_manager: ChatSessionManager = None


def init_app(ollash_root_dir: Path, event_publisher):
    """Initialize the ChatSessionManager for this blueprint."""
    global _session_manager
    _session_manager = ChatSessionManager(ollash_root_dir, event_publisher)


@chat_bp.route("/api/chat", methods=["POST"])
@require_api_key
@rate_limit_chat
def send_chat():
    """Send a message to a chat session.

    Body JSON: { "message": "...", "session_id": "..." (optional), "project_path": "..." (optional), "agent_type": "..." (optional) }
    Returns: { "session_id": "...", "status": "started" }
    """
    data = request.get_json(force=True)
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"status": "error", "message": "Message is required."}), 400

    session_id = data.get("session_id")
    project_path = data.get("project_path")
    agent_type = data.get("agent_type")

    try:
        if not session_id or _session_manager.get_session(session_id) is None:
            session_id = _session_manager.create_session(project_path, agent_type)

        _session_manager.send_message(session_id, message)
        return jsonify({"status": "started", "session_id": session_id})
    except RuntimeError as e:
        return jsonify({"status": "error", "message": str(e)}), 429
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@chat_bp.route("/api/chat/stream/<session_id>")
def stream_chat(session_id):
    """SSE endpoint that streams chat events for a given session."""
    session = _session_manager.get_session(session_id)
    if session is None:
        return jsonify({"status": "error", "message": "Session not found."}), 404

    return Response(
        stream_with_context(session.bridge.iter_events()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
