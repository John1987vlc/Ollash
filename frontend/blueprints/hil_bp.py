from flask import Blueprint, jsonify, request
from backend.utils.core.event_publisher import EventPublisher

hil_bp = Blueprint("hil", __name__)

@hil_bp.route("/api/hil/respond", methods=["POST"])
def respond_hil():
    """Submits a response to a Human-in-the-loop approval request."""
    data = request.json
    request_id = data.get("request_id")
    response = data.get("response") # "approve", "reject", "correct"
    feedback = data.get("feedback", "")
    
    if not request_id or not response:
        return jsonify({"error": "Missing request_id or response"}), 400
        
    # Publish response event so the waiting agent can continue
    publisher = EventPublisher()
    publisher.publish("hil_response", {
        "request_id": request_id,
        "response": response,
        "feedback": feedback
    })
    
    return jsonify({"status": "success"})
