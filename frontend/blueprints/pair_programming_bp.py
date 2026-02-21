"""Blueprint for Live Pair Programming Mode (F12)."""

import json
import logging

from flask import Blueprint, Response, jsonify, request

logger = logging.getLogger(__name__)

pair_programming_bp = Blueprint("pair_programming_bp", __name__, url_prefix="/api/pair-programming")

_event_publisher = None
_sessions = {}


def init_app(app, event_publisher=None):
    """Initialize pair programming blueprint."""
    global _event_publisher
    _event_publisher = event_publisher or app.config.get("event_publisher")
    logger.info("Pair programming blueprint initialized")


@pair_programming_bp.route("/sessions", methods=["POST"])
def create_session():
    """Create a new pair programming session."""
    if not _event_publisher:
        return jsonify({"error": "Event publisher not available"}), 503

    try:
        from backend.utils.core.feedback.pair_programming_session import PairProgrammingSession
        from backend.core.containers import main_container

        import uuid

        session_id = str(uuid.uuid4())[:8]
        session = PairProgrammingSession(
            session_id=session_id,
            event_publisher=_event_publisher,
            logger=main_container.core.logger(),
        )
        _sessions[session_id] = session
        return jsonify({"session_id": session_id, "status": "active"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@pair_programming_bp.route("/sessions/<session_id>", methods=["GET"])
def get_session(session_id):
    """Get session stats."""
    session = _sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(session.get_session_stats())


@pair_programming_bp.route("/sessions/<session_id>/pause", methods=["POST"])
def pause_session(session_id):
    """Pause a pair programming session."""
    session = _sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    session.pause()
    return jsonify({"status": "paused"})


@pair_programming_bp.route("/sessions/<session_id>/resume", methods=["POST"])
def resume_session(session_id):
    """Resume a paused pair programming session."""
    session = _sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    session.resume()
    return jsonify({"status": "resumed"})


@pair_programming_bp.route("/sessions/<session_id>/intervene", methods=["POST"])
def user_intervene(session_id):
    """Submit a user edit intervention."""
    session = _sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    data = request.get_json(force=True)
    content = data.get("content", "")
    cursor_pos = data.get("cursor_position", -1)
    session.user_intervention(content, cursor_pos)
    return jsonify({"status": "intervention_recorded"})


@pair_programming_bp.route("/sessions/<session_id>/end", methods=["POST"])
def end_session(session_id):
    """End a pair programming session."""
    session = _sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    session.end_session()
    _sessions.pop(session_id, None)
    return jsonify({"status": "ended"})


@pair_programming_bp.route("/sessions/<session_id>/stream", methods=["GET"])
def stream_session(session_id):
    """SSE stream for pair programming updates."""
    session = _sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    def event_stream():
        import queue

        q = queue.Queue()

        def on_event(event_type, **kwargs):
            if kwargs.get("session_id") == session_id:
                q.put(json.dumps({"type": event_type, **kwargs}))

        events = [
            "pair_programming_update",
            "pair_programming_file_start",
            "pair_programming_file_complete",
            "pair_programming_paused",
            "pair_programming_resumed",
            "pair_programming_ended",
            "pair_programming_intervention",
        ]
        for evt in events:
            _event_publisher.subscribe(evt, on_event)

        try:
            while session.is_active:
                try:
                    data = q.get(timeout=15)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            for evt in events:
                _event_publisher.unsubscribe(evt, on_event)

    return Response(event_stream(), mimetype="text/event-stream")
