"""Blueprint for triggering proactive monitoring agents."""

import asyncio
import logging

from flask import Blueprint, jsonify, request

from backend.agents.monitor_agents import create_monitor_agents
from backend.utils.core.system.event_publisher import EventPublisher
from frontend.middleware import require_api_key

logger = logging.getLogger(__name__)

monitors_bp = Blueprint("monitors", __name__)

_monitor_agents = None
_event_publisher = None


def init_app(app, event_publisher: EventPublisher):
    """Initialize monitors blueprint."""
    global _monitor_agents, _event_publisher
    ollash_root_dir = app.config.get("ollash_root_dir")
    _event_publisher = event_publisher
    _monitor_agents = create_monitor_agents(ollash_root_dir, event_publisher)


@monitors_bp.route("/api/monitors/available", methods=["GET"])
@require_api_key
def get_available_monitors():
    """Get list of available monitoring agents."""
    return jsonify(
        {
            "monitors": [
                {
                    "id": "system",
                    "name": "System Monitor",
                    "description": "Health checks, cleanup, log analysis",
                    "capabilities": ["health_check", "cleanup", "analyze_logs"],
                },
                {
                    "id": "network",
                    "name": "Network Monitor",
                    "description": "Uptime checks, port monitoring",
                    "capabilities": ["check_services_uptime", "detect_port_issues"],
                },
                {
                    "id": "security",
                    "name": "Security Monitor",
                    "description": "Integrity scanning, vulnerability checks",
                    "capabilities": [
                        "integrity_scan",
                        "security_log_analysis",
                        "vulnerability_scan",
                    ],
                },
            ]
        }
    )


@monitors_bp.route("/api/monitors/system/health-check", methods=["POST"])
@require_api_key
def run_system_health_check():
    """Run system health check."""
    if not _monitor_agents:
        return jsonify({"error": "Monitor agents not initialized"}), 503

    try:

        def _run_check():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(_monitor_agents["system"].perform_health_check())
                return result
            finally:
                loop.close()

        # Execute in background thread
        result = _run_check()

        return jsonify({"status": "completed", "check_type": "system_health", "result": result})

    except Exception as e:
        logger.error(f"Error running system health check: {e}")
        return jsonify({"error": str(e)}), 500


@monitors_bp.route("/api/monitors/system/cleanup", methods=["POST"])
@require_api_key
def run_system_cleanup():
    """Run system cleanup scan."""
    if not _monitor_agents:
        return jsonify({"error": "Monitor agents not initialized"}), 503

    try:

        def _run_cleanup():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(_monitor_agents["system"].cleanup_system())
                return result
            finally:
                loop.close()

        result = _run_cleanup()

        return jsonify({"status": "completed", "check_type": "system_cleanup", "result": result})

    except Exception as e:
        logger.error(f"Error running system cleanup: {e}")
        return jsonify({"error": str(e)}), 500


@monitors_bp.route("/api/monitors/system/logs", methods=["POST"])
@require_api_key
def analyze_system_logs():
    """Analyze system logs."""
    if not _monitor_agents:
        return jsonify({"error": "Monitor agents not initialized"}), 503

    try:
        data = request.get_json() if request.is_json else {}
        patterns = data.get("patterns")

        def _run_analysis():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(_monitor_agents["system"].analyze_logs(patterns))
                return result
            finally:
                loop.close()

        result = _run_analysis()

        return jsonify({"status": "completed", "check_type": "log_analysis", "result": result})

    except Exception as e:
        logger.error(f"Error analyzing logs: {e}")
        return jsonify({"error": str(e)}), 500


@monitors_bp.route("/api/monitors/network/uptime", methods=["POST"])
@require_api_key
def check_network_uptime():
    """Check network services uptime."""
    if not _monitor_agents:
        return jsonify({"error": "Monitor agents not initialized"}), 503

    try:
        data = request.get_json() if request.is_json else {}
        services = data.get("services")

        def _run_check():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(_monitor_agents["network"].check_services_uptime(services))
                return result
            finally:
                loop.close()

        result = _run_check()

        return jsonify({"status": "completed", "check_type": "network_uptime", "result": result})

    except Exception as e:
        logger.error(f"Error checking network uptime: {e}")
        return jsonify({"error": str(e)}), 500


@monitors_bp.route("/api/monitors/network/ports", methods=["POST"])
@require_api_key
def detect_port_issues():
    """Detect port issues."""
    if not _monitor_agents:
        return jsonify({"error": "Monitor agents not initialized"}), 503

    try:
        data = request.get_json() if request.is_json else {}
        ports = data.get("ports")

        def _run_check():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(_monitor_agents["network"].detect_port_issues(ports))
                return result
            finally:
                loop.close()

        result = _run_check()

        return jsonify({"status": "completed", "check_type": "port_detection", "result": result})

    except Exception as e:
        logger.error(f"Error detecting port issues: {e}")
        return jsonify({"error": str(e)}), 500


@monitors_bp.route("/api/monitors/security/integrity", methods=["POST"])
@require_api_key
def run_integrity_scan():
    """Run file integrity scan."""
    if not _monitor_agents:
        return jsonify({"error": "Monitor agents not initialized"}), 503

    try:
        data = request.get_json() if request.is_json else {}
        file_paths = data.get("files")

        def _run_scan():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(_monitor_agents["security"].integrity_scan(file_paths))
                return result
            finally:
                loop.close()

        result = _run_scan()

        return jsonify({"status": "completed", "check_type": "integrity_scan", "result": result})

    except Exception as e:
        logger.error(f"Error running integrity scan: {e}")
        return jsonify({"error": str(e)}), 500


@monitors_bp.route("/api/monitors/security/logs", methods=["POST"])
@require_api_key
def analyze_security_logs():
    """Analyze security logs."""
    if not _monitor_agents:
        return jsonify({"error": "Monitor agents not initialized"}), 503

    try:

        def _run_analysis():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(_monitor_agents["security"].security_log_analysis())
                return result
            finally:
                loop.close()

        result = _run_analysis()

        return jsonify(
            {
                "status": "completed",
                "check_type": "security_log_analysis",
                "result": result,
            }
        )

    except Exception as e:
        logger.error(f"Error analyzing security logs: {e}")
        return jsonify({"error": str(e)}), 500


@monitors_bp.route("/api/monitors/security/vulnerabilities", methods=["POST"])
@require_api_key
def scan_vulnerabilities():
    """Scan for vulnerabilities."""
    if not _monitor_agents:
        return jsonify({"error": "Monitor agents not initialized"}), 503

    try:

        def _run_scan():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(_monitor_agents["security"].vulnerability_scan())
                return result
            finally:
                loop.close()

        result = _run_scan()

        return jsonify(
            {
                "status": "completed",
                "check_type": "vulnerability_scan",
                "result": result,
            }
        )

    except Exception as e:
        logger.error(f"Error scanning vulnerabilities: {e}")
        return jsonify({"error": str(e)}), 500
