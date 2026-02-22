from flask import Blueprint, jsonify, request
import uuid
import datetime

hil_bp = Blueprint("hil", __name__)

# In-memory store for pending requests (for the demo/UI)
# In a production scenario, this would be managed by a global ConfirmationManager
_pending_requests = {}

@hil_bp.route("/api/hil/pending", methods=["GET"])
def get_pending():
    """Returns a list of all pending HIL requests."""
    requests_list = []
    for req_id, req in _pending_requests.items():
        requests_list.append({
            "id": req_id,
            "type": req.get("type"),
            "title": req.get("title"),
            "details": req.get("details"),
            "timestamp": req.get("timestamp"),
            "agent": req.get("agent", "DefaultAgent")
        })
    return jsonify(sorted(requests_list, key=lambda x: x["timestamp"], reverse=True))

@hil_bp.route("/api/hil/respond", methods=["POST"])
def respond_hil():
    """Submits a response to a Human-in-the-loop approval request."""
    data = request.json
    request_id = data.get("request_id")
    response = data.get("response")  # "approve", "reject", "correct"
    feedback = data.get("feedback", "")

    if not request_id or not response:
        return jsonify({"error": "Missing request_id or response"}), 400

    if request_id in _pending_requests:
        # Mark as responded and remove (or keep in a history)
        _pending_requests[request_id]["status"] = response
        _pending_requests[request_id]["feedback"] = feedback
        # For now, we just remove it from pending
        del _pending_requests[request_id]

    # In a real integration, we would notify the waiting agent here via EventPublisher
    from backend.utils.core.system.event_publisher import EventPublisher
    publisher = EventPublisher()
    publisher.publish("hil_response", {"request_id": request_id, "response": response, "feedback": feedback})

    return jsonify({"status": "success"})

# Helper for testing/dev to inject a request
@hil_bp.route("/api/hil/debug/add", methods=["POST"])
def add_debug_request():
    data = request.json
    req_id = str(uuid.uuid4())[:8]
    _pending_requests[req_id] = {
        "type": data.get("type", "write_file"),
        "title": data.get("title", "Modificar archivo"),
        "details": data.get("details", {}),
        "timestamp": datetime.datetime.now().isoformat(),
        "agent": data.get("agent", "AutoAgent")
    }
    return jsonify({"id": req_id})
