"""
Blueprint for Swarm/Cowork endpoints.
Exposes functionality from CoworkTools for knowledge workspace operations.
"""

import os
from pathlib import Path
from flask import Blueprint, current_app, jsonify, request

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.structured_logger import StructuredLogger
from backend.utils.core.io.documentation_manager import DocumentationManager
from backend.utils.core.llm.ollama_client import OllamaClient
from backend.utils.core.llm.llm_recorder import LLMRecorder
from backend.utils.domains.bonus.cowork_impl import CoworkTools

swarm_bp = Blueprint("swarm", __name__, url_prefix="/api/swarm")

def get_swarm_managers():
    """Returns or creates the swarm managers."""
    if not hasattr(current_app, "_swarm_managers"):
        project_root = current_app.config.get("ollash_root_dir", Path.cwd())
        config = current_app.config.get("config", {})

        # Setup Logger
        log_path = project_root / ".ollash" / "logs" / "swarm.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        structured_logger = StructuredLogger(log_path, "swarm")
        agent_logger = AgentLogger(structured_logger, "SwarmAgent")

        # LLM Recorder
        llm_recorder = LLMRecorder(agent_logger)

        # Ollama Client
        ollama_url = os.environ.get("OLLASH_OLLAMA_URL", config.get("ollama_url", "http://localhost:11434"))
        ollama_client = OllamaClient(
            url=ollama_url,
            model=config.get("model", "qwen3-coder:30b"),
            timeout=config.get("timeout", 300),
            logger=agent_logger,
            config=config,
            llm_recorder=llm_recorder
        )

        # Documentation Manager
        doc_manager = DocumentationManager(project_root, agent_logger, llm_recorder, config)

        # Cowork Tools
        workspace_path = project_root / ".ollash" / "knowledge_workspace"
        cowork_tools = CoworkTools(doc_manager, ollama_client, agent_logger, workspace_path)

        current_app._swarm_managers = {
            "tools": cowork_tools,
            "logger": agent_logger
        }

    return current_app._swarm_managers

@swarm_bp.route("/doc-to-task", methods=["POST"])
def doc_to_task():
    """Converts a document to automation tasks."""
    try:
        data = request.get_json()
        if not data or "document_name" not in data:
            return jsonify({"status": "error", "message": "Missing document_name"}), 400

        doc_name = data["document_name"]
        category = data.get("category", "automation")
        priority = data.get("priority", "medium")

        managers = get_swarm_managers()
        result = managers["tools"].document_to_task(doc_name, category, priority)

        return jsonify(result), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@swarm_bp.route("/analyze-logs", methods=["POST"])
def analyze_logs():
    """Analyzes recent logs for risks."""
    try:
        data = request.get_json() or {}
        log_type = data.get("log_type", "system")
        period = data.get("time_period", "24hours")
        threshold = data.get("risk_threshold", "high")

        managers = get_swarm_managers()
        result = managers["tools"].analyze_recent_logs(log_type, period, threshold)

        return jsonify(result), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@swarm_bp.route("/executive-summary", methods=["POST"])
def executive_summary():
    """Generates an executive summary of a document."""
    try:
        data = request.get_json()
        if not data or "document_name" not in data:
            return jsonify({"status": "error", "message": "Missing document_name"}), 400

        doc_name = data["document_name"]
        summary_type = data.get("summary_type", "executive")

        managers = get_swarm_managers()
        result = managers["tools"].generate_executive_summary(doc_name, summary_type)

        return jsonify(result), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def init_app(app):
    """Initializes the blueprint."""
    app.logger.info("✓ Swarm blueprint initialized")
