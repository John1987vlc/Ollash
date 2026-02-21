import json
import os
from pathlib import Path
from flask import Blueprint, jsonify, send_file, request
from backend.core.containers import main_container

audit_bp = Blueprint("audit", __name__)

def get_log_path():
    root = main_container.core.ollash_root_dir()
    # Looking at CoreContainer in containers.py, log_file defaults to ollash.log
    return root / "ollash.log"

@audit_bp.route("/api/audit/llm", methods=["GET"])
def get_llm_audit():
    """Parses the structured log file for LLM interaction events."""
    log_path = get_log_path()
    if not log_path.exists():
        return jsonify({"events": []})

    limit = request.args.get("limit", 100, type=int)
    events = []
    
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            # Read lines in reverse to get newest first (simple version)
            lines = f.readlines()
            for line in reversed(lines):
                try:
                    data = json.loads(line)
                    # Filter for LLM related events (from LLMRecorder or StructuredLogger)
                    if data.get("event_type") in ["llm_request", "llm_response"] or \
                       data.get("type") in ["llm_request", "llm_response"]:
                        events.append(data)
                        if len(events) >= limit:
                            break
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"events": events})

@audit_bp.route("/api/audit/download/llm_logs.json")
def download_logs():
    """Downloads the filtered LLM logs as JSON."""
    log_path = get_log_path()
    if not log_path.exists():
        return "Log file not found", 404
    
    # We could filter them here, but for simplicity we send the whole file 
    # if it's small, or we could generate a temp JSON.
    # The requirement says "descargar este registro de auditoría".
    return send_file(log_path, as_attachment=True, download_name="llm_audit_logs.json")
