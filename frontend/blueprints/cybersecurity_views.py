"""
Blueprint for cybersecurity endpoints.
Exposes functionality from CybersecurityTools and VulnerabilityScanner.
"""

from pathlib import Path
from flask import Blueprint, current_app, jsonify, request
from pydantic import ValidationError

from frontend.schemas.cybersecurity_schemas import (
    IntegrityCheckRequest,
    LogAnalysisRequest,
    PortScanRequest,
    VulnScanRequest,
)
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.structured_logger import StructuredLogger
from backend.utils.core.command_executor import CommandExecutor
from backend.utils.core.io.file_manager import FileManager
from backend.utils.domains.cybersecurity.cybersecurity_tools import CybersecurityTools
from backend.utils.core.analysis.vulnerability_scanner import VulnerabilityScanner

bp = Blueprint("cybersecurity", __name__, url_prefix="/api/cybersecurity")


def get_cybersecurity_managers():
    """Returns or creates the cybersecurity managers."""
    if not hasattr(current_app, "_cybersecurity_managers"):
        project_root = current_app.config.get("ollash_root_dir", Path.cwd())

        # Setup Logger
        log_path = project_root / "logs" / "cybersecurity.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        structured_logger = StructuredLogger(log_path, "cybersecurity")
        agent_logger = AgentLogger(structured_logger, "CybersecurityAgent")

        exec_cmd = CommandExecutor(project_root, agent_logger)
        file_mgr = FileManager(project_root, agent_logger)

        current_app._cybersecurity_managers = {
            "tools": CybersecurityTools(exec_cmd, file_mgr, agent_logger),
            "scanner": VulnerabilityScanner(agent_logger),
            "logger": agent_logger,
        }

    return current_app._cybersecurity_managers


@bp.route("/scan/ports", methods=["POST"])
def scan_ports():
    """
    Performs a port scan on a target host.
    Payload: { "host": "localhost", "common_ports_only": true }
    """
    try:
        body = PortScanRequest.model_validate(request.get_json() or {})
    except ValidationError as exc:
        return jsonify({"ok": False, "error": exc.errors()}), 422

    try:
        managers = get_cybersecurity_managers()
        result = managers["tools"].scan_ports(body.host, body.common_ports_only)
        return jsonify(result), 200
    except Exception as e:
        current_app.logger.error(f"Error in scan_ports: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/scan/vulnerabilities", methods=["POST"])
def scan_vulnerabilities():
    """
    Scans a file for security vulnerabilities.
    Payload: { "path": "src/app.py" }
    """
    try:
        body = VulnScanRequest.model_validate(request.get_json() or {})
    except ValidationError as exc:
        return jsonify({"ok": False, "error": exc.errors()}), 422

    try:
        project_root = current_app.config.get("ollash_root_dir", Path.cwd())
        full_path = project_root / body.path

        if not full_path.exists():
            return jsonify({"ok": False, "error": f"File not found: {body.path}"}), 404

        content = full_path.read_text(encoding="utf-8", errors="ignore")

        managers = get_cybersecurity_managers()
        result = managers["scanner"].scan_file(body.path, content)

        return jsonify({"ok": True, "result": result.to_dict()}), 200
    except Exception as e:
        current_app.logger.error(f"Error in scan_vulnerabilities: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/integrity/check", methods=["POST"])
def check_integrity():
    """
    Checks file integrity using hashes.
    Payload: { "path": "file.txt", "expected_hash": "...", "algorithm": "sha256" }
    """
    try:
        body = IntegrityCheckRequest.model_validate(request.get_json() or {})
    except ValidationError as exc:
        return jsonify({"ok": False, "error": exc.errors()}), 422

    try:
        managers = get_cybersecurity_managers()
        res = managers["tools"].check_file_hash(body.path, body.algorithm)

        if res["ok"]:
            actual_hash = res["result"]["hash"]
            match = actual_hash.lower() == body.expected_hash.lower()
            res["result"]["match"] = match
            res["result"]["expected_hash"] = body.expected_hash

        return jsonify(res), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/logs/analyze", methods=["POST"])
def analyze_logs():
    """
    Analyzes security logs for anomalies.
    Payload: { "path": "logs/auth.log", "keywords": ["FAILED"] }
    """
    try:
        body = LogAnalysisRequest.model_validate(request.get_json() or {})
    except ValidationError as exc:
        return jsonify({"ok": False, "error": exc.errors()}), 422

    try:
        managers = get_cybersecurity_managers()
        result = managers["tools"].analyze_security_log(body.path, body.keywords)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/recommendations", methods=["GET"])
def get_recommendations():
    """
    Provides security hardening recommendations.
    Query param: ?os=Linux
    """
    try:
        os_type = request.args.get("os", "Linux")
        managers = get_cybersecurity_managers()
        result = managers["tools"].recommend_security_hardening(os_type)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def init_app(app):
    """Initializes the blueprint."""
    app.logger.info("✓ Cybersecurity blueprint initialized")
