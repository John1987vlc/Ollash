"""Blueprint for Model Cost Analyzer (F8).

Provides cost reports, model suggestions, and real-time cost streaming.
"""

import json
import logging
import queue
import time

from flask import Blueprint, Response, jsonify, request

logger = logging.getLogger(__name__)

cost_bp = Blueprint("cost_bp", __name__, url_prefix="/api/costs")

_cost_analyzer = None
_cost_event_queue = queue.Queue(maxsize=100)


def init_app(app):
    """Initialize cost analyzer blueprint."""
    global _cost_analyzer
    try:
        from backend.core.containers import main_container
        from backend.utils.core.analysis.cost_analyzer import CostAnalyzer

        _cost_analyzer = CostAnalyzer(
            token_tracker=None,
            llm_config=main_container.auto_agent_module.llm_models_config(),
            logger=main_container.core.logger(),
        )
        logger.info("Cost analyzer initialized")
    except Exception as e:
        logger.warning(f"Cost analyzer init skipped: {e}")


def push_cost_event(data):
    """Push a cost update event for SSE streaming."""
    try:
        _cost_event_queue.put_nowait(data)
    except queue.Full:
        pass


@cost_bp.route("/report", methods=["GET"])
def get_cost_report():
    """Get cost report."""
    if not _cost_analyzer:
        return jsonify({"error": "Cost analyzer not available"}), 503

    try:
        report = _cost_analyzer.get_report()
        return jsonify({"report": report.to_dict() if hasattr(report, "to_dict") else report})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@cost_bp.route("/suggestions", methods=["GET"])
def get_suggestions():
    """Get model downgrade suggestions."""
    if not _cost_analyzer:
        return jsonify({"suggestions": []})

    try:
        suggestions = _cost_analyzer.suggest_downgrades()
        return jsonify({"suggestions": [s.to_dict() if hasattr(s, "to_dict") else s for s in suggestions]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@cost_bp.route("/by-model", methods=["GET"])
def get_costs_by_model():
    """Get token usage breakdown by model."""
    if not _cost_analyzer:
        return jsonify({"by_model": {}})

    try:
        report = _cost_analyzer.get_report()
        report_dict = report.to_dict() if hasattr(report, "to_dict") else report
        return jsonify({"by_model": report_dict.get("by_model", {})})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@cost_bp.route("/by-phase", methods=["GET"])
def get_costs_by_phase():
    """Get token usage breakdown by phase."""
    if not _cost_analyzer:
        return jsonify({"by_phase": {}})

    try:
        report = _cost_analyzer.get_report()
        report_dict = report.to_dict() if hasattr(report, "to_dict") else report
        return jsonify({"by_phase": report_dict.get("by_phase", {})})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@cost_bp.route("/history", methods=["GET"])
def get_cost_history():
    """Get historical token usage data."""
    if not _cost_analyzer:
        return jsonify({"history": []})

    try:
        limit = request.args.get("limit", 50, type=int)
        report = _cost_analyzer.get_report()
        report_dict = report.to_dict() if hasattr(report, "to_dict") else report
        history = report_dict.get("history", [])
        return jsonify({"history": history[:limit]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@cost_bp.route("/stream", methods=["GET"])
def cost_stream():
    """SSE endpoint for real-time cost updates."""

    def generate():
        while True:
            try:
                data = _cost_event_queue.get(timeout=30)
                yield f"event: cost_update\ndata: {json.dumps(data)}\n\n"
            except queue.Empty:
                yield f"event: ping\ndata: {json.dumps({'ts': time.time()})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
