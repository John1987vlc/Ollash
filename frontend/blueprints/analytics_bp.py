"""
Analytics Blueprint — P10: Metacognition & Analytics Dashboard.

Endpoints:
    GET /api/analytics/projects          List projects with aggregated DAG stats.
    GET /api/analytics/projects/<name>   Per-node breakdown for a project.
    GET /api/analytics/lessons           Lessons from EpisodicMemory / ErrorKnowledgeBase.
    GET /analytics                       Renders the analytics dashboard page.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Blueprint, current_app, jsonify, render_template

analytics_bp = Blueprint("analytics", __name__)

# Lazily resolved from app config
_metrics_db = None
_episodic_memory = None


def _get_metrics_db():
    global _metrics_db
    if _metrics_db is None:
        _metrics_db = current_app.config.get("metrics_database")
    return _metrics_db


def _get_episodic_memory():
    global _episodic_memory
    if _episodic_memory is None:
        _episodic_memory = current_app.config.get("episodic_memory")
    return _episodic_memory


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------


@analytics_bp.route("/analytics")
def analytics_page():
    return render_template("pages/analytics.html")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@analytics_bp.route("/api/analytics/projects")
def list_projects():
    """Aggregated stats for all recorded projects (last 50)."""
    db = _get_metrics_db()
    if db is None:
        return jsonify([])

    try:
        records: List[Dict[str, Any]] = db.get_metric_history(
            "dag", "project_completed", hours=24 * 365, limit=50
        )

        projects = []
        for r in records:
            val = r.get("value", {})
            projects.append(
                {
                    "project_name": val.get("project_name", "unknown"),
                    "total_tokens": val.get("total_tokens", 0),
                    "total_files": val.get("total_files", 0),
                    "failed_count": val.get("failed_count", 0),
                    "timestamp": r.get("timestamp", ""),
                }
            )

        # Most-recent first
        projects.sort(key=lambda p: p["timestamp"], reverse=True)
        return jsonify(projects)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@analytics_bp.route("/api/analytics/projects/<project_name>")
def project_detail(project_name: str):
    """Per-node breakdown for a specific project."""
    db = _get_metrics_db()
    if db is None:
        return jsonify([])

    try:
        records: List[Dict[str, Any]] = db.get_metric_history(
            "dag", "node_completed", hours=24 * 365, limit=500
        )

        nodes = []
        for r in records:
            val = r.get("value", {})
            if val.get("project_name") == project_name:
                nodes.append(
                    {
                        "task_id": val.get("task_id", ""),
                        "agent_type": val.get("agent_type", ""),
                        "duration_ms": val.get("duration_ms", 0),
                        "tokens": val.get("tokens", 0),
                        "retry_count": val.get("retry_count", 0),
                        "timestamp": r.get("timestamp", ""),
                    }
                )

        return jsonify(nodes)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@analytics_bp.route("/api/analytics/lessons")
def list_lessons():
    """Lessons from EpisodicMemory and/or ErrorKnowledgeBase."""
    mem = _get_episodic_memory()
    lessons: List[Dict[str, Any]] = []

    if mem is not None:
        try:
            recent = getattr(mem, "get_recent_episodes", None)
            if recent:
                for ep in recent(limit=30):
                    lessons.append(
                        {
                            "date": ep.get("timestamp", ""),
                            "agent": ep.get("agent_id", "unknown"),
                            "error_pattern": ep.get("error_type", ep.get("summary", "")),
                            "fix_applied": ep.get("resolution", ep.get("outcome", "")),
                        }
                    )
        except Exception:
            pass

    # Fallback: read from ErrorKnowledgeBase if accessible
    if not lessons:
        ekb = current_app.config.get("error_knowledge_base")
        if ekb is not None:
            try:
                get_all = getattr(ekb, "get_all_patterns", None)
                if get_all:
                    for pat in get_all():
                        lessons.append(
                            {
                                "date": pat.get("last_seen", ""),
                                "agent": pat.get("agent_type", "unknown"),
                                "error_pattern": pat.get("pattern", ""),
                                "fix_applied": pat.get("suggested_fix", ""),
                            }
                        )
            except Exception:
                pass

    return jsonify(lessons)


@analytics_bp.route("/api/analytics/summary")
def summary():
    """High-level KPI summary for the dashboard cards."""
    db = _get_metrics_db()
    totals: Dict[str, Any] = {
        "total_projects": 0,
        "total_tokens": 0,
        "total_files": 0,
        "total_failed": 0,
        "agent_type_counts": {},
    }

    if db is None:
        return jsonify(totals)

    try:
        proj_records = db.get_metric_history(
            "dag", "project_completed", hours=24 * 365
        )
        for r in proj_records:
            val = r.get("value", {})
            totals["total_projects"] += 1
            totals["total_tokens"] += val.get("total_tokens", 0)
            totals["total_files"] += val.get("total_files", 0)
            totals["total_failed"] += val.get("failed_count", 0)

        node_records = db.get_metric_history(
            "dag", "node_completed", hours=24 * 365
        )
        for r in node_records:
            val = r.get("value", {})
            agent_type = val.get("agent_type", "unknown")
            totals["agent_type_counts"][agent_type] = (
                totals["agent_type_counts"].get(agent_type, 0) + 1
            )

    except Exception:
        pass

    return jsonify(totals)
