"""Blueprint for system metrics dashboard and analytics."""

import logging
from pathlib import Path

from flask import Blueprint, jsonify, request

from backend.utils.core.metrics_database import get_metrics_database
from frontend.middleware import require_api_key

logger = logging.getLogger(__name__)

metrics_bp = Blueprint("metrics", __name__)

_metrics_db = None


def init_app(ollash_root_dir: Path):
    """Initialize metrics blueprint."""
    global _metrics_db
    _metrics_db = get_metrics_database(ollash_root_dir)


@metrics_bp.route("/api/metrics/categories", methods=["GET"])
@require_api_key
def get_metric_categories():
    """Get available metric categories."""
    return jsonify(
        {
            "categories": [
                {"id": "system", "name": "System Metrics", "icon": "🖥️"},
                {"id": "network", "name": "Network Metrics", "icon": "🌐"},
                {"id": "security", "name": "Security Metrics", "icon": "🔒"},
            ]
        }
    )


@metrics_bp.route("/api/metrics/<category>", methods=["GET"])
@require_api_key
def get_category_metrics(category: str):
    """Get all metrics for a category."""
    hours = request.args.get("hours", 24, type=int)

    try:
        # Get metric files for this category
        if not _metrics_db:
            return jsonify({"error": "Metrics database not initialized"}), 503

        metric_files = list(_metrics_db.db_path.glob(f"{category}_*.json"))

        metrics = []
        for metric_file in metric_files:
            # Extract metric name from filename
            metric_name = metric_file.stem.replace(f"{category}_", "")

            # Get latest value
            latest = _metrics_db.get_latest_metric(category, metric_name)
            if latest:
                stats = _metrics_db.get_metric_stats(category, metric_name, hours=hours)

                metrics.append(
                    {
                        "name": metric_name,
                        "latest_value": latest.get("value"),
                        "latest_timestamp": latest.get("timestamp"),
                        "stats": stats,
                        "unit": _get_metric_unit(category, metric_name),
                    }
                )

        return jsonify({"category": category, "hours": hours, "metrics": metrics})

    except Exception as e:
        logger.error(f"Error retrieving metrics for {category}: {e}")
        return jsonify({"error": str(e)}), 500


@metrics_bp.route("/api/metrics/<category>/<metric_name>", methods=["GET"])
@require_api_key
def get_metric_history(category: str, metric_name: str):
    """Get historical data for a specific metric."""
    hours = request.args.get("hours", 24, type=int)
    limit = request.args.get("limit", 100, type=int)

    try:
        if not _metrics_db:
            return jsonify({"error": "Metrics database not initialized"}), 503

        history = _metrics_db.get_metric_history(category, metric_name, hours=hours, limit=limit)

        return jsonify(
            {
                "category": category,
                "metric": metric_name,
                "hours": hours,
                "records": history,
                "count": len(history),
            }
        )

    except Exception as e:
        logger.error(f"Error retrieving history for {category}/{metric_name}: {e}")
        return jsonify({"error": str(e)}), 500


@metrics_bp.route("/api/metrics/<category>/<metric_name>/stats", methods=["GET"])
@require_api_key
def get_metric_statistics(category: str, metric_name: str):
    """Get statistics for a metric."""
    hours = request.args.get("hours", 24, type=int)

    try:
        if not _metrics_db:
            return jsonify({"error": "Metrics database not initialized"}), 503

        stats = _metrics_db.get_metric_stats(category, metric_name, hours=hours)

        if not stats:
            return jsonify({"error": "No data available"}), 404

        return jsonify(
            {
                "category": category,
                "metric": metric_name,
                "period_hours": hours,
                "statistics": stats,
            }
        )

    except Exception as e:
        logger.error(f"Error calculating stats: {e}")
        return jsonify({"error": str(e)}), 500


@metrics_bp.route("/api/metrics/dashboard/summary", methods=["GET"])
@require_api_key
def get_dashboard_summary():
    """Get summary view of all metrics for dashboard."""
    hours = request.args.get("hours", 24, type=int)

    try:
        if not _metrics_db:
            return jsonify({"error": "Metrics database not initialized"}), 503

        categories = ["system", "network", "security"]
        summary = {}

        for category in categories:
            metric_files = list(_metrics_db.db_path.glob(f"{category}_*.json"))
            category_metrics = []

            for metric_file in metric_files:
                metric_name = metric_file.stem.replace(f"{category}_", "")
                latest = _metrics_db.get_latest_metric(category, metric_name)

                if latest:
                    category_metrics.append(
                        {
                            "name": metric_name,
                            "value": latest.get("value"),
                            "timestamp": latest.get("timestamp"),
                        }
                    )

            if category_metrics:
                summary[category] = {
                    "count": len(category_metrics),
                    "latest_metrics": category_metrics[:5],  # Last 5 metrics
                }

        return jsonify(
            {
                "timestamp": __import__("datetime").datetime.now().isoformat(),
                "period_hours": hours,
                "summary": summary,
            }
        )

    except Exception as e:
        logger.error(f"Error getting dashboard summary: {e}")
        return jsonify({"error": str(e)}), 500


@metrics_bp.route("/api/metrics/cleanup", methods=["POST"])
@require_api_key
def cleanup_old_metrics():
    """Cleanup old metrics (default: 30 days old)."""
    days = request.get_json().get("days", 30) if request.is_json else 30

    try:
        if not _metrics_db:
            return jsonify({"error": "Metrics database not initialized"}), 503

        _metrics_db.clear_old_metrics(days=days)

        return jsonify({"status": "success", "message": f"Cleaned metrics older than {days} days"})

    except Exception as e:
        logger.error(f"Error cleaning metrics: {e}")
        return jsonify({"error": str(e)}), 500


def _get_metric_unit(category: str, metric_name: str) -> str:
    """Get the unit for a metric."""
    units = {
        "cpu": "%",
        "memory": "MB",
        "disk": "GB",
        "usage": "%",
        "free": "MB",
        "latency": "ms",
        "count": "count",
    }

    for key, unit in units.items():
        if key in metric_name.lower():
            return unit

    return ""
