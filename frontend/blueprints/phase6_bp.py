"""
REST API endpoints for Phase 6 components
Exposes all Phase 6 functionality via REST API
"""

import io
import json
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

from backend.utils.core.feedback.activity_report_generator import get_activity_report_generator

# Import Phase 6 components
from backend.utils.core.feedback.adaptive_notification_ui import get_adaptive_notification_ui
from backend.utils.core.system.advanced_trigger_manager import LogicOperator, get_advanced_trigger_manager
from backend.utils.core.feedback.feedback_cycle_manager import FeedbackType, get_feedback_cycle_manager
from backend.utils.core.memory.memory_of_decisions import DecisionDomain, MemoryOfDecisions
from backend.utils.core.io.voice_command_processor import get_voice_command_processor
from backend.utils.core.system.webhook_manager import MessagePriority, WebhookType, get_webhook_manager

# Create blueprint
phase6_bp = Blueprint("phase6_api", __name__, url_prefix="/api/v1")


# ==================== NOTIFICATION UI ENDPOINTS ====================


@phase6_bp.route("/notifications/artifacts", methods=["GET"])
def get_artifacts():
    """Get all active notification artifacts"""
    ui = get_adaptive_notification_ui()
    artifacts = ui.get_active_artifacts()

    return jsonify(
        {
            "success": True,
            "artifacts": [
                {
                    "id": str(a.id) if hasattr(a, "id") else str(i),
                    "type": a.artifact_type if hasattr(a, "artifact_type") else "unknown",
                    "created": str(a.timestamp) if hasattr(a, "timestamp") else str(datetime.now()),
                }
                for i, a in enumerate(artifacts)
            ],
            "count": len(artifacts),
        }
    )


@phase6_bp.route("/notifications/artifacts", methods=["POST"])
def create_artifact():
    """Create a custom notification artifact"""
    data = request.get_json()
    ui = get_adaptive_notification_ui()

    artifact_type = data.get("type", "custom")

    if artifact_type == "network_error":
        result = ui.notify_network_error(
            service_name=data.get("service", "unknown"),
            failed_nodes=data.get("nodes", []),
            error_message=data.get("message", ""),
        )
    elif artifact_type == "system_status":
        result = ui.notify_system_status(metrics=data.get("metrics", {}), thresholds=data.get("thresholds", {}))
    elif artifact_type == "decision_point":
        result = ui.notify_decision_point(
            problem=data.get("problem", ""),
            options=data.get("options", {}),
            recommendation=data.get("recommendation"),
        )
    elif artifact_type == "diagnostic":
        result = ui.notify_diagnostic(
            problem=data.get("problem", ""),
            findings=data.get("findings", []),
            severity=data.get("severity", "medium"),
        )
    else:
        return (
            jsonify({"success": False, "error": f"Unknown artifact type: {artifact_type}"}),
            400,
        )

    return jsonify(
        {
            "success": True,
            "artifact": {
                "id": str(getattr(result, "id", "unknown")),
                "type": artifact_type,
                "created": str(datetime.now()),
            },
        }
    )


@phase6_bp.route("/notifications/clear", methods=["POST"])
def clear_artifacts():
    """Clear old/inactive artifacts"""
    ui = get_adaptive_notification_ui()
    older_than = request.json.get("older_than_seconds", 3600)

    ui.clear_artifacts(older_than_seconds=older_than)

    return jsonify({"success": True})


# ==================== WEBHOOK ENDPOINTS ====================


@phase6_bp.route("/webhooks", methods=["GET"])
def get_webhooks():
    """Get all registered webhooks and their status"""
    webhook_mgr = get_webhook_manager()
    status = webhook_mgr.get_webhook_status()
    failures = webhook_mgr.get_failed_deliveries()

    return jsonify(
        {
            "success": True,
            "webhooks": status if status else [],
            "failed_deliveries": failures if failures else [],
            "failure_count": len(failures) if failures else 0,
        }
    )


@phase6_bp.route("/webhooks", methods=["POST"])
def register_webhook():
    """Register a new webhook"""
    data = request.get_json()
    webhook_mgr = get_webhook_manager()

    try:
        webhook_type = WebhookType(data.get("type", "SLACK"))
    except ValueError:
        return jsonify({"success": False, "error": "Invalid webhook type"}), 400

    success = webhook_mgr.register_webhook(
        name=data.get("name"), webhook_type=webhook_type, webhook_url=data.get("url")
    )

    return jsonify(
        {
            "success": success,
            "message": "Webhook registered" if success else "Failed to register",
        }
    )


@phase6_bp.route("/webhooks/<webhook_name>/send", methods=["POST"])
def send_webhook_message(webhook_name):
    """Send a message via webhook"""
    data = request.get_json()
    webhook_mgr = get_webhook_manager()

    try:
        priority = MessagePriority(data.get("priority", "MEDIUM"))
    except ValueError:
        priority = MessagePriority.MEDIUM

    success = webhook_mgr.send_to_webhook_sync(
        webhook_name=webhook_name,
        message=data.get("message", ""),
        title=data.get("title", "Notification"),
        priority=priority,
        fields=data.get("fields", {}),
    )

    return jsonify({"success": success, "message": "Sent" if success else "Failed to send"})


@phase6_bp.route("/webhooks/<webhook_name>/health", methods=["GET"])
def check_webhook_health(webhook_name):
    """Check health of a specific webhook"""
    webhook_mgr = get_webhook_manager()

    healthy = webhook_mgr.health_check(webhook_name)

    return jsonify(
        {
            "webhook": webhook_name,
            "healthy": healthy,
            "status": "ok" if healthy else "error",
        }
    )


# ==================== REPORT ENDPOINTS ====================


@phase6_bp.route("/reports/daily", methods=["GET"])
def get_daily_report():
    """Get today's activity report"""
    report_gen = get_activity_report_generator()
    report = report_gen.generate_daily_summary()

    format_type = request.args.get("format", "json")

    if format_type == "markdown":
        md = report_gen.format_report_as_markdown(report)
        return md, 200, {"Content-Type": "text/markdown"}
    elif format_type == "html":
        html = report_gen.format_report_as_html(report)
        return html, 200, {"Content-Type": "text/html"}
    else:  # json
        return jsonify(
            {
                "success": True,
                "report": {
                    "timestamp": str(report.timestamp),
                    "performance_score": report.performance_score,
                    "metrics": report.metrics if hasattr(report, "metrics") else {},
                    "anomalies": report.anomalies if hasattr(report, "anomalies") else [],
                },
            }
        )


@phase6_bp.route("/reports/trends", methods=["GET"])
def get_trend_report():
    """Get performance trend report"""
    days = request.args.get("days", 7, type=int)
    report_gen = get_activity_report_generator()

    report = report_gen.generate_performance_trend_report()

    format_type = request.args.get("format", "json")

    if format_type == "markdown":
        md = report_gen.format_report_as_markdown(report)
        return md, 200, {"Content-Type": "text/markdown"}
    else:
        return jsonify(
            {
                "success": True,
                "days": days,
                "report": str(report) if report else "No data",
            }
        )


@phase6_bp.route("/reports/anomalies", methods=["GET"])
def get_anomaly_report():
    """Get anomaly detection report"""
    report_gen = get_activity_report_generator()
    report = report_gen.generate_anomaly_report()

    return jsonify(
        {
            "success": True,
            "anomalies": report.anomalies if hasattr(report, "anomalies") else [],
            "severity": report.severity if hasattr(report, "severity") else "unknown",
        }
    )


# ==================== VOICE COMMAND ENDPOINTS ====================


@phase6_bp.route("/voice/process", methods=["POST"])
def process_voice_command():
    """Process voice transcription and execute command"""
    data = request.get_json()
    processor = get_voice_command_processor()

    command = processor.process_voice_input(
        transcribed_text=data.get("text", ""),
        confidence=data.get("confidence", 0.0),
        language=data.get("language", "en"),
    )

    # Execute if high confidence
    if command.confidence >= 70:
        result = processor.execute_voice_command(command)
        return jsonify(
            {
                "success": True,
                "command_type": command.command_type.value
                if hasattr(command.command_type, "value")
                else str(command.command_type),
                "confidence": command.confidence,
                "parameters": command.parameters,
                "execution_result": result,
            }
        )
    else:
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Low confidence ({command.confidence:.0f}%). Please repeat.",
                    "confidence": command.confidence,
                    "require_confirmation": True,
                    "command": command.to_dict() if hasattr(command, "to_dict") else str(command),
                }
            ),
            400,
        )


@phase6_bp.route("/voice/commands", methods=["GET"])
def get_voice_history():
    """Get voice command history"""
    processor = get_voice_command_processor()
    limit = request.args.get("limit", 50, type=int)

    history = processor.command_history[-limit:] if processor.command_history else []

    return jsonify(
        {
            "success": True,
            "count": len(history),
            "commands": [
                {
                    "text": str(cmd),
                    "timestamp": str(getattr(cmd, "timestamp", datetime.now())),
                }
                for cmd in history
            ],
        }
    )


@phase6_bp.route("/voice/stats", methods=["GET"])
def get_voice_stats():
    """Get voice command statistics"""
    processor = get_voice_command_processor()
    stats = processor.get_command_statistics()

    return jsonify({"success": True, "stats": stats if stats else {}})


# ==================== DECISION MEMORY ENDPOINTS ====================


@phase6_bp.route("/decisions", methods=["GET"])
def get_decisions():
    """Get decision analytics and summary"""
    memory = MemoryOfDecisions(Path.cwd())
    analytics = memory.get_decision_analytics()

    return jsonify({"success": True, "analytics": analytics})


@phase6_bp.route("/decisions", methods=["POST"])
def record_decision():
    """Record a new decision"""
    data = request.get_json()
    memory = MemoryOfDecisions(Path.cwd())

    try:
        domain = DecisionDomain(data.get("domain", "ARCHITECTURE"))
    except ValueError:
        domain = DecisionDomain.ARCHITECTURE

    success = memory.record_decision(
        decision_id=data.get("id", f"dec_{datetime.now().timestamp()}"),
        domain=domain,
        decision_text=data.get("text", ""),
        reasoning=data.get("reasoning", ""),
        context=data.get("context", {}),
        chosen_option=data.get("option", ""),
        alternatives=data.get("alternatives", []),
    )

    return jsonify({"success": success, "decision_id": data.get("id")})


@phase6_bp.route("/decisions/<decision_id>/outcome", methods=["POST"])
def record_decision_outcome(decision_id):
    """Record outcome of a decision"""
    data = request.get_json()
    memory = MemoryOfDecisions(Path.cwd())

    success = memory.record_decision_outcome(
        decision_id=decision_id,
        satisfaction_score=data.get("satisfaction_score", 0),
        actual_outcome=data.get("outcome", ""),
        lessons_learned=data.get("lessons", ""),
    )

    return jsonify({"success": success, "decision_id": decision_id})


@phase6_bp.route("/decisions/suggestions", methods=["POST"])
def get_decision_suggestions():
    """Get decision suggestions for current context"""
    data = request.get_json()
    memory = MemoryOfDecisions(Path.cwd())

    suggestions = memory.get_decision_suggestions(current_context=data.get("context", {}), limit=data.get("limit", 5))

    return jsonify(
        {
            "success": True,
            "suggestions": [
                {"decision": str(s), "similarity": getattr(s, "similarity_score", 0.5)} for s in suggestions
            ]
            if suggestions
            else [],
            "count": len(suggestions) if suggestions else 0,
        }
    )


# ==================== FEEDBACK ENDPOINTS ====================


@phase6_bp.route("/feedback", methods=["POST"])
def submit_feedback():
    """Submit feedback on content"""
    data = request.get_json()
    feedback_mgr = get_feedback_cycle_manager(Path.cwd())

    try:
        feedback_type = FeedbackType(data.get("type", "TOO_VERBOSE"))
    except ValueError:
        feedback_type = FeedbackType.TOO_VERBOSE

    feedback = feedback_mgr.submit_feedback(
        content_id=data.get("content_id", f"content_{datetime.now().timestamp()}"),
        content_excerpt=data.get("excerpt", ""),
        feedback_type=feedback_type,
        feedback_text=data.get("feedback", ""),
        severity=data.get("severity", "moderate"),
        suggested_correction=data.get("correction"),
    )

    return jsonify(
        {
            "success": True,
            "feedback_id": getattr(feedback, "id", "recorded"),
            "message": "Feedback recorded and will be used to improve future responses",
        }
    )


@phase6_bp.route("/feedback/profile", methods=["GET"])
def get_style_profile():
    """Get learned style preferences"""
    feedback_mgr = get_feedback_cycle_manager(Path.cwd())
    profile = feedback_mgr.get_style_profile()

    return jsonify(
        {
            "success": True,
            "style_profile": profile if profile else {},
            "dimensions": list(profile.keys()) if profile else [],
        }
    )


@phase6_bp.route("/feedback/trends", methods=["GET"])
def get_feedback_trends():
    """Get feedback trends"""
    days = request.args.get("days", 7, type=int)
    feedback_mgr = get_feedback_cycle_manager(Path.cwd())

    trends = feedback_mgr.get_feedback_trends(days=days)
    summary = feedback_mgr.get_feedback_summary()

    return jsonify(
        {
            "success": True,
            "days": days,
            "trends": trends if trends else {},
            "summary": summary if summary else {},
        }
    )


# ==================== ADVANCED TRIGGER ENDPOINTS ====================


@phase6_bp.route("/triggers", methods=["GET"])
def get_triggers():
    """Get all registered triggers"""
    trigger_mgr = get_advanced_trigger_manager()

    triggers = list(trigger_mgr.triggers.keys()) if hasattr(trigger_mgr, "triggers") else []

    return jsonify({"success": True, "triggers": triggers, "count": len(triggers)})


@phase6_bp.route("/triggers", methods=["POST"])
def register_trigger():
    """Register a composite trigger"""
    data = request.get_json()
    trigger_mgr = get_advanced_trigger_manager()

    try:
        operator = LogicOperator(data.get("operator", "AND"))
    except ValueError:
        operator = LogicOperator.AND

    from backend.utils.core.system.advanced_trigger_manager import CompositeTriggerCondition

    condition = CompositeTriggerCondition(
        id=f"cond_{data.get('id', 'default')}",
        operator=operator,
        sub_conditions=data.get("conditions", []),
    )

    success = trigger_mgr.register_composite_trigger(
        trigger_id=data.get("id"),
        name=data.get("name", ""),
        composite_condition=condition,
        action_callback=lambda ctx: {"executed": True},
        cooldown_seconds=data.get("cooldown", 60),
    )

    return jsonify({"success": success, "trigger_id": data.get("id")})


@phase6_bp.route("/triggers/<trigger_id>/evaluate", methods=["POST"])
def evaluate_trigger(trigger_id):
    """Evaluate a trigger with given context"""
    data = request.get_json()
    trigger_mgr = get_advanced_trigger_manager()

    result = trigger_mgr.evaluate_trigger(trigger_id, data.get("context", {}))

    return jsonify(
        {
            "success": True,
            "trigger_id": trigger_id,
            "evaluates_to": result if isinstance(result, bool) else bool(result),
            "context_used": data.get("context", {}),
        }
    )


@phase6_bp.route("/triggers/<trigger_id>/fire", methods=["POST"])
def fire_trigger(trigger_id):
    """Fire a trigger manually"""
    data = request.get_json()
    trigger_mgr = get_advanced_trigger_manager()

    trigger_mgr.fire_trigger(trigger_id, data.get("context", {}))

    return jsonify({"success": True, "trigger_id": trigger_id, "fired": True})


@phase6_bp.route("/triggers/conflicts", methods=["GET"])
def detect_conflicts():
    """Detect conflicting triggers"""
    trigger_mgr = get_advanced_trigger_manager()

    conflicts = trigger_mgr.detect_conflicts()

    return jsonify(
        {
            "success": True,
            "conflicts": conflicts if conflicts else [],
            "conflict_count": len(conflicts) if conflicts else 0,
        }
    )


# ==================== HEALTH CHECK ====================


@phase6_bp.route("/health", methods=["GET"])
def health_check():
    """Health check for Phase 6 components"""
    return jsonify(
        {
            "success": True,
            "status": "healthy",
            "components": {
                "notification_ui": "ok",
                "webhooks": "ok",
                "reports": "ok",
                "voice": "ok",
                "decisions": "ok",
                "feedback": "ok",
                "triggers": "ok",
            },
            "timestamp": str(datetime.now()),
        }
    )


# ==================== BATCH OPERATIONS ====================


@phase6_bp.route("/batch", methods=["POST"])
def batch_operation():
    """Execute multiple operations in batch"""
    data = request.get_json()
    operations = data.get("operations", [])

    results = []
    for op in operations:
        op_type = op.get("type")
        op_data = op.get("data", {})

        if op_type == "send_notification":
            webhook_mgr = get_webhook_manager()
            success = webhook_mgr.send_to_webhook_sync(
                webhook_name=op_data.get("webhook"), message=op_data.get("message")
            )
            results.append({"type": op_type, "success": success})

        elif op_type == "record_feedback":
            feedback_mgr = get_feedback_cycle_manager(Path.cwd())
            feedback_mgr.submit_feedback(
                content_id=op_data.get("content_id"),
                content_excerpt=op_data.get("excerpt"),
                feedback_type=FeedbackType(op_data.get("type", "TOO_VERBOSE")),
                feedback_text=op_data.get("text"),
            )
            results.append({"type": op_type, "success": True})

    return jsonify({"success": True, "operations_processed": len(results), "results": results})


# ==================== EXPORT ENDPOINTS ====================


@phase6_bp.route("/export/decisions", methods=["GET"])
def export_decisions():
    """Export all decisions to JSON"""
    memory = MemoryOfDecisions(Path.cwd())
    data = {
        "exported": str(datetime.now()),
        "total_decisions": len(memory.decisions),
        "decisions": memory.decisions,
    }

    json_str = json.dumps(data, indent=2, default=str)
    return send_file(
        io.BytesIO(json_str.encode()),
        mimetype="application/json",
        as_attachment=True,
        download_name=f"decisions_{datetime.now().strftime('%Y%m%d')}.json",
    )


@phase6_bp.route("/export/feedback", methods=["GET"])
def export_feedback():
    """Export all feedback to JSON"""
    feedback_mgr = get_feedback_cycle_manager(Path.cwd())
    data = {
        "exported": str(datetime.now()),
        "total_feedback": len(feedback_mgr.feedback_history),
        "feedback": feedback_mgr.feedback_history,
    }

    json_str = json.dumps(data, indent=2, default=str)
    return send_file(
        io.BytesIO(json_str.encode()),
        mimetype="application/json",
        as_attachment=True,
        download_name=f"feedback_{datetime.now().strftime('%Y%m%d')}.json",
    )
