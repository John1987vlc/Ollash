"""
Blueprint para artefactos interactivos.

Expone endpoints para crear y renderizar diferentes tipos de artefactos
que se mostrarán en el panel derecho de la UI.
"""

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.artifact_manager import ArtifactManager

artifacts_bp = Blueprint("artifacts", __name__, url_prefix="/api/artifacts")


def get_artifact_manager():
    """Obtiene o crea el ArtifactManager."""
    if not hasattr(current_app, "_artifact_manager"):
        logger = current_app.config.get("logger", AgentLogger("artifacts"))
        project_root = current_app.config.get("ollash_root_dir", Path.cwd())
        config = current_app.config.get("config", {})

        current_app._artifact_manager = ArtifactManager(project_root, logger, config)

    return current_app._artifact_manager


# ============ CRUD Endpoints ============


@artifacts_bp.route("/", methods=["GET"])
def list_artifacts():
    """
    Lista todos los artefactos.

    Query params:
    - type: Filtrar por tipo (report, diagram, checklist, code, comparison)
    """
    try:
        artifact_type = request.args.get("type")

        manager = get_artifact_manager()
        artifacts = manager.list_artifacts(artifact_type)

        return (
            jsonify(
                {
                    "count": len(artifacts),
                    "type_filter": artifact_type,
                    "artifacts": [a.to_dict() for a in artifacts],
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"Error listing artifacts: {e}")
        return jsonify({"error": str(e)}), 500


@artifacts_bp.route("/<artifact_id>", methods=["GET"])
def get_artifact(artifact_id):
    """Obtiene un artefacto específico."""
    try:
        manager = get_artifact_manager()
        artifact = manager.get_artifact(artifact_id)

        if not artifact:
            return jsonify({"error": "Artifact not found"}), 404

        return jsonify(artifact.to_dict()), 200

    except Exception as e:
        current_app.logger.error(f"Error getting artifact: {e}")
        return jsonify({"error": str(e)}), 500


@artifacts_bp.route("/<artifact_id>", methods=["DELETE"])
def delete_artifact(artifact_id):
    """Elimina un artefacto."""
    try:
        manager = get_artifact_manager()
        success = manager.delete_artifact(artifact_id)

        if not success:
            return jsonify({"error": "Artifact not found"}), 404

        return jsonify({"status": "deleted"}), 200

    except Exception as e:
        current_app.logger.error(f"Error deleting artifact: {e}")
        return jsonify({"error": str(e)}), 500


# ============ Report Endpoints ============


@artifacts_bp.route("/report", methods=["POST"])
def create_report():
    """
    Crea un informe.

    Payload:
    {
        "title": "Network Analysis Report",
        "sections": [
            {"heading": "Executive Summary", "content": "..."},
            {"heading": "Findings", "content": "..."}
        ],
        "metadata": {"theme": "light"}
    }
    """
    try:
        data = request.get_json()

        if not data or "title" not in data or "sections" not in data:
            return jsonify({"error": "Missing title or sections"}), 400

        manager = get_artifact_manager()
        artifact_id = manager.create_report(
            title=data["title"],
            sections=data["sections"],
            metadata=data.get("metadata"),
        )

        return jsonify({"status": "created", "artifact_id": artifact_id}), 201

    except Exception as e:
        current_app.logger.error(f"Error creating report: {e}")
        return jsonify({"error": str(e)}), 500


# ============ Diagram Endpoints ============


@artifacts_bp.route("/diagram", methods=["POST"])
def create_diagram():
    """
    Crea un diagrama Mermaid.

    Payload:
    {
        "title": "System Architecture",
        "mermaid_code": "graph LR\n    A-->B",
        "diagram_type": "graph",
        "metadata": {}
    }
    """
    try:
        data = request.get_json()

        if not data or "title" not in data or "mermaid_code" not in data:
            return jsonify({"error": "Missing title or mermaid_code"}), 400

        manager = get_artifact_manager()
        artifact_id = manager.create_diagram(
            title=data["title"],
            mermaid_code=data["mermaid_code"],
            diagram_type=data.get("diagram_type", "graph"),
            metadata=data.get("metadata"),
        )

        return jsonify({"status": "created", "artifact_id": artifact_id}), 201

    except Exception as e:
        current_app.logger.error(f"Error creating diagram: {e}")
        return jsonify({"error": str(e)}), 500


# ============ Checklist Endpoints ============


@artifacts_bp.route("/checklist", methods=["POST"])
def create_checklist():
    """
    Crea un checklist.

    Payload:
    {
        "title": "Security Checklist",
        "items": [
            {"id": "auth", "label": "Enable authentication", "completed": false},
            {"id": "ssl", "label": "Configure SSL", "completed": true}
        ],
        "metadata": {}
    }
    """
    try:
        data = request.get_json()

        if not data or "title" not in data or "items" not in data:
            return jsonify({"error": "Missing title or items"}), 400

        manager = get_artifact_manager()
        artifact_id = manager.create_checklist(title=data["title"], items=data["items"], metadata=data.get("metadata"))

        return jsonify({"status": "created", "artifact_id": artifact_id}), 201

    except Exception as e:
        current_app.logger.error(f"Error creating checklist: {e}")
        return jsonify({"error": str(e)}), 500


@artifacts_bp.route("/<artifact_id>/checklist-item/<item_id>", methods=["PUT"])
def update_checklist_item(artifact_id, item_id):
    """
    Actualiza un item de checklist.

    Payload:
    {
        "completed": true
    }
    """
    try:
        data = request.get_json()

        if not data or "completed" not in data:
            return jsonify({"error": "Missing completed status"}), 400

        manager = get_artifact_manager()
        success = manager.update_checklist_item(artifact_id, item_id, data["completed"])

        if not success:
            return jsonify({"error": "Failed to update item"}), 400

        # Retornar el artifact actualizado
        artifact = manager.get_artifact(artifact_id)
        return jsonify(artifact.to_dict()), 200

    except Exception as e:
        current_app.logger.error(f"Error updating checklist item: {e}")
        return jsonify({"error": str(e)}), 500


# ============ Code Endpoints ============


@artifacts_bp.route("/code", methods=["POST"])
def create_code():
    """
    Crea un artefacto de código.

    Payload:
    {
        "title": "Example Function",
        "code": "def hello():\\n    print('Hello')",
        "language": "python",
        "metadata": {}
    }
    """
    try:
        data = request.get_json()

        if not data or "title" not in data or "code" not in data:
            return jsonify({"error": "Missing title or code"}), 400

        manager = get_artifact_manager()
        artifact_id = manager.create_code_artifact(
            title=data["title"],
            code=data["code"],
            language=data.get("language", "python"),
            metadata=data.get("metadata"),
        )

        return jsonify({"status": "created", "artifact_id": artifact_id}), 201

    except Exception as e:
        current_app.logger.error(f"Error creating code artifact: {e}")
        return jsonify({"error": str(e)}), 500


# ============ Comparison Endpoints ============


@artifacts_bp.route("/comparison", methods=["POST"])
def create_comparison():
    """
    Crea una tabla de comparación.

    Payload:
    {
        "title": "Database Comparison",
        "items": [
            {
                "name": "PostgreSQL",
                "values": {
                    "Scalability": "High",
                    "Cost": "Low",
                    "Performance": "Excellent"
                }
            },
            {
                "name": "MongoDB",
                "values": {
                    "Scalability": "Very High",
                    "Cost": "Medium",
                    "Performance": "Good"
                }
            }
        ],
        "characteristics": ["Scalability", "Cost", "Performance"],
        "metadata": {}
    }
    """
    try:
        data = request.get_json()

        required = ["title", "items", "characteristics"]
        if not data or not all(k in data for k in required):
            return jsonify({"error": f"Missing required fields: {required}"}), 400

        manager = get_artifact_manager()
        artifact_id = manager.create_comparison(
            title=data["title"],
            items=data["items"],
            characteristics=data["characteristics"],
            metadata=data.get("metadata"),
        )

        return jsonify({"status": "created", "artifact_id": artifact_id}), 201

    except Exception as e:
        current_app.logger.error(f"Error creating comparison: {e}")
        return jsonify({"error": str(e)}), 500


# ============ Rendering Endpoints ============


@artifacts_bp.route("/<artifact_id>/render", methods=["GET"])
def render_artifact(artifact_id):
    """
    Renderiza un artefacto a HTML.

    Response:
    {
        "html": "<div>...</div>",
        "type": "report",
        "title": "Report Title"
    }
    """
    try:
        manager = get_artifact_manager()
        artifact = manager.get_artifact(artifact_id)

        if not artifact:
            return jsonify({"error": "Artifact not found"}), 404

        html = manager.render_artifact_html(artifact_id)

        return (
            jsonify(
                {
                    "html": html,
                    "type": artifact.type,
                    "title": artifact.title,
                    "artifact_id": artifact_id,
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"Error rendering artifact: {e}")
        return jsonify({"error": str(e)}), 500


@artifacts_bp.route("/render-batch", methods=["POST"])
def render_batch():
    """
    Renderiza múltiples artefactos en una sola solicitud.

    Payload:
    {
        "artifact_ids": ["art_123", "art_456"]
    }
    """
    try:
        data = request.get_json()

        if not data or "artifact_ids" not in data:
            return jsonify({"error": "Missing artifact_ids"}), 400

        manager = get_artifact_manager()
        results = {}

        for artifact_id in data["artifact_ids"]:
            artifact = manager.get_artifact(artifact_id)
            if artifact:
                html = manager.render_artifact_html(artifact_id)
                results[artifact_id] = {
                    "html": html,
                    "type": artifact.type,
                    "title": artifact.title,
                }

        return jsonify({"count": len(results), "rendered": results}), 200

    except Exception as e:
        current_app.logger.error(f"Error rendering batch: {e}")
        return jsonify({"error": str(e)}), 500


def init_app(app):
    """Inicializa el blueprint con la app."""
    app.logger.info("✓ Artifacts blueprint registered")
