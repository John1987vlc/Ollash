"""
Phase 4: Refinement Blueprint
Flask blueprint exposing refinement workflow capabilities via REST API
"""

from flask import Blueprint, request, jsonify
from pathlib import Path
from backend.utils.core.feedback_refinement_manager import FeedbackRefinementManager
from backend.utils.core.source_validator import SourceValidator
from backend.utils.core.refinement_orchestrator import RefinementOrchestrator


# Initialize managers
refinement_manager = None
validator = None
orchestrator = None


def init_refinement(app=None):
    """Initialize refinement managers"""
    global refinement_manager, validator, orchestrator

    workspace = Path(app.config.get('KNOWLEDGE_WORKSPACE', 'knowledge_workspace'))
    refinement_manager = FeedbackRefinementManager(str(workspace))
    validator = SourceValidator(str(workspace))
    orchestrator = RefinementOrchestrator(str(workspace))


# Create blueprint
refinement_bp = Blueprint('refinement', __name__, url_prefix='/api/refinement')


# =====================
# WORKFLOW MANAGEMENT
# =====================

@refinement_bp.route('/workflow/create', methods=['POST'])
def create_workflow():
    """
    Create a new refinement workflow

    Request Body:
    {
        "workflow_id": "string",
        "source_id": "string",
        "document_text": "string",
        "strategy": "comprehensive" | "quick_polish" | "accuracy_focused"
    }
    """
    try:
        data = request.get_json()
        workflow_id = data.get("workflow_id")
        source_id = data.get("source_id")
        document_text = data.get("document_text")
        strategy = data.get("strategy", "comprehensive")

        if not all([workflow_id, source_id, document_text]):
            return jsonify({"error": "Missing required fields"}), 400

        workflow = orchestrator.create_workflow(
            workflow_id=workflow_id,
            source_id=source_id,
            document_text=document_text,
            strategy=strategy
        )

        return jsonify({
            "status": "success",
            "workflow": workflow.to_dict()
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@refinement_bp.route('/workflow/<workflow_id>/analyze', methods=['GET'])
def analyze_workflow(workflow_id):
    """Analyze document and identify refinement candidates"""
    try:
        analysis = orchestrator.analyze_document(workflow_id)
        return jsonify({
            "status": "success",
            "analysis": analysis
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@refinement_bp.route('/workflow/<workflow_id>/refine', methods=['POST'])
def refine_workflow(workflow_id):
    """
    Execute refinement workflow

    Request Body:
    {
        "strategy": "comprehensive",
        "paragraph_indices": [0, 1, 2]  # optional, null = all
    }
    """
    try:
        data = request.get_json() or {}
        strategy = data.get("strategy", "comprehensive")
        indices = data.get("paragraph_indices")

        results = orchestrator.refine_workflow(
            workflow_id=workflow_id,
            strategy_name=strategy,
            paragraph_indices=indices
        )

        return jsonify({
            "status": "success",
            "results": results
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@refinement_bp.route('/workflow/<workflow_id>/status', methods=['GET'])
def get_workflow_status(workflow_id):
    """Get current status of workflow"""
    try:
        status = orchestrator.get_workflow_status(workflow_id)
        if "error" in status:
            return jsonify(status), 404
        return jsonify({
            "status": "success",
            "workflow": status
        }), 200
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@refinement_bp.route('/workflow/list', methods=['GET'])
def list_workflows():
    """List all workflows"""
    try:
        workflows = orchestrator.list_workflows()
        return jsonify({
            "status": "success",
            "count": len(workflows),
            "workflows": workflows
        }), 200
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@refinement_bp.route('/workflow/<workflow_id>/export', methods=['GET'])
def export_workflow(workflow_id):
    """
    Export refined document

    Query Parameters:
    - format: "text" | "markdown" | "html" (default: "text")
    """
    try:
        format_type = request.args.get("format", "text")
        content = orchestrator.export_workflow_document(workflow_id, format_type)

        # Set appropriate content type
        content_types = {
            "text": "text/plain",
            "markdown": "text/markdown",
            "html": "text/html"
        }

        return content, 200, {"Content-Type": content_types.get(format_type, "text/plain")}
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# =====================
# PARAGRAPH REFINEMENT
# =====================

@refinement_bp.route('/paragraph/critique', methods=['POST'])
def critique_paragraph():
    """
    Generate critique for a paragraph

    Request Body:
    {
        "text": "string",
        "source_id": "string",
        "critique_type": "clarity" | "conciseness" | "accuracy" | "structure"
    }
    """
    try:
        data = request.get_json()
        text = data.get("text")
        source_id = data.get("source_id", "default")
        critique_type = data.get("critique_type", "clarity")

        if not text:
            return jsonify({"error": "Missing text"}), 400

        from .utils.core.feedback_refinement_manager import ParagraphContext

        para = ParagraphContext(
            index=0,
            text=text,
            original_text=text,
            source_id=source_id
        )

        critique = refinement_manager.generate_critique(para, critique_type)

        return jsonify({
            "status": "success",
            "critique_type": critique_type,
            "critique": critique,
            "readability_score": para.readability_score
        }), 200
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@refinement_bp.route('/paragraph/compare', methods=['POST'])
def compare_paragraphs():
    """
    Compare original and refined versions

    Request Body:
    {
        "original": "string",
        "refined": "string"
    }
    """
    try:
        data = request.get_json()
        original = data.get("original")
        refined = data.get("refined")

        if not original or not refined:
            return jsonify({"error": "Missing original or refined text"}), 400

        comparison = validator.compare_versions(original, refined)

        return jsonify({
            "status": "success",
            "comparison": comparison
        }), 200
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# =====================
# VALIDATION
# =====================

@refinement_bp.route('/validate', methods=['POST'])
def validate_refinement():
    """
    Validate a refinement against source

    Request Body:
    {
        "original_text": "string",
        "refined_text": "string",
        "source_id": "string",
        "validation_type": "full" | "semantic" | "factual"
    }
    """
    try:
        data = request.get_json()
        original = data.get("original_text")
        refined = data.get("refined_text")
        source_id = data.get("source_id")
        val_type = data.get("validation_type", "full")

        if not all([original, refined, source_id]):
            return jsonify({"error": "Missing required fields"}), 400

        result = validator.validate_refinement(
            original_text=original,
            refined_text=refined,
            source_id=source_id,
            validation_type=val_type
        )

        return jsonify({
            "status": "success",
            "is_valid": result.is_valid,
            "validation_score": result.validation_score,
            "confidence": result.confidence_level,
            "issue_count": len(result.issues),
            "issues": [issue.to_dict() for issue in result.issues]
        }), 200
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@refinement_bp.route('/validation/report', methods=['GET'])
def get_validation_report():
    """Get overall validation statistics"""
    try:
        report = validator.get_validation_report()
        return jsonify({
            "status": "success",
            "report": report
        }), 200
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# =====================
# SOURCE MANAGEMENT
# =====================

@refinement_bp.route('/source/register', methods=['POST'])
def register_source():
    """
    Register a source document

    Request Body:
    {
        "source_id": "string",
        "source_text": "string"
    }
    """
    try:
        data = request.get_json()
        source_id = data.get("source_id")
        source_text = data.get("source_text")

        if not source_id or not source_text:
            return jsonify({"error": "Missing required fields"}), 400

        success = validator.register_source(source_id, source_text)

        return jsonify({
            "status": "success" if success else "failed",
            "source_id": source_id
        }), 201 if success else 400
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@refinement_bp.route('/source/<source_id>', methods=['GET'])
def get_source(source_id):
    """Retrieve a registered source"""
    try:
        source = validator.get_source(source_id)
        if not source:
            return jsonify({"error": f"Source '{source_id}' not found"}), 404

        return jsonify({
            "status": "success",
            "source_id": source_id,
            "content": source
        }), 200
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# =====================
# REFINEMENT METRICS
# =====================

@refinement_bp.route('/metrics/summary', methods=['GET'])
def get_refinement_summary():
    """Get overall refinement metrics"""
    try:
        summary = refinement_manager.get_refinement_summary()
        return jsonify({
            "status": "success",
            "metrics": summary
        }), 200
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@refinement_bp.route('/strategies', methods=['GET'])
def list_strategies():
    """List available refinement strategies"""
    try:
        strategies = [
            {
                "name": strategy.name,
                "description": strategy.description,
                "critique_types": strategy.critique_types,
                "iteration_limit": strategy.iteration_limit
            }
            for strategy in orchestrator.STRATEGIES.values()
        ]

        return jsonify({
            "status": "success",
            "count": len(strategies),
            "strategies": strategies
        }), 200
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# =====================
# ERROR HANDLERS
# =====================

@refinement_bp.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return jsonify({"error": "Resource not found"}), 404


@refinement_bp.errorhandler(500)
def internal_error(e):
    """Handle 500 errors"""
    return jsonify({"error": "Internal server error"}), 500
