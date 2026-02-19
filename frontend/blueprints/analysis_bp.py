"""
Blueprint for advanced analysis endpoints.

Expone funcionalidades de:
- Cross-Reference Analysis
- Knowledge Graphs
- Decision Context
"""

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.cross_reference_analyzer import CrossReferenceAnalyzer
from backend.utils.core.decision_context_manager import DecisionContextManager
from backend.utils.core.knowledge_graph_builder import KnowledgeGraphBuilder

analysis_bp = Blueprint("analysis", __name__, url_prefix="/api/analysis")


def get_analysis_managers():
    """Obtiene o crea los managers de análisis."""
    if not hasattr(current_app, "_analysis_managers"):
        logger = current_app.config.get("logger", AgentLogger("analysis"))
        project_root = current_app.config.get("ollash_root_dir", Path.cwd())
        config = current_app.config.get("config", {})

        current_app._analysis_managers = {
            "cross_ref": CrossReferenceAnalyzer(project_root, logger, config),
            "knowledge_graph": KnowledgeGraphBuilder(project_root, logger, config),
            "decision_context": DecisionContextManager(project_root, logger, config),
        }

    return current_app._analysis_managers


# ============ Cross-Reference Endpoints ============


@analysis_bp.route("/cross-reference/compare", methods=["POST"])
def compare_documents():
    """
    Compara dos documentos.

    Payload:
    {
        "doc1_path": "docs/network_manual.md",
        "doc2_path": "config/network_config.json"
    }
    """
    try:
        data = request.get_json()

        if not data or "doc1_path" not in data or "doc2_path" not in data:
            return jsonify({"error": "Missing doc1_path or doc2_path"}), 400

        project_root = current_app.config.get("ollash_root_dir", Path.cwd())
        doc1 = project_root / data["doc1_path"]
        doc2 = project_root / data["doc2_path"]

        managers = get_analysis_managers()
        result = managers["cross_ref"].compare_documents(doc1, doc2)

        return jsonify(result), 200

    except Exception as e:
        current_app.logger.error(f"Error in compare_documents: {e}")
        return jsonify({"error": str(e)}), 500


@analysis_bp.route("/cross-reference/find-references", methods=["POST"])
def find_cross_references():
    """
    Busca referencias cruzadas de un término.

    Payload:
    {
        "term": "API",
        "source_dirs": ["docs", "src"],
        "context_window": 100
    }
    """
    try:
        data = request.get_json()

        if not data or "term" not in data:
            return jsonify({"error": "Missing term"}), 400

        term = data["term"]
        source_dirs = data.get("source_dirs", ["docs"])
        context_window = data.get("context_window", 100)

        project_root = current_app.config.get("ollash_root_dir", Path.cwd())
        source_paths = [project_root / d for d in source_dirs]

        managers = get_analysis_managers()
        references = managers["cross_ref"].find_cross_references(term, source_paths, context_window)

        return (
            jsonify(
                {
                    "term": term,
                    "count": len(references),
                    "references": [r.to_dict() for r in references],
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"Error in find_cross_references: {e}")
        return jsonify({"error": str(e)}), 500


@analysis_bp.route("/cross-reference/inconsistencies", methods=["POST"])
def find_inconsistencies():
    """
    Busca inconsistencias en documentos.

    Payload:
    {
        "doc_paths": ["docs/README.md", "docs/ARCHITECTURE.md"]
    }
    """
    try:
        data = request.get_json()

        if not data or "doc_paths" not in data:
            return jsonify({"error": "Missing doc_paths"}), 400

        project_root = current_app.config.get("ollash_root_dir", Path.cwd())
        doc_paths = [project_root / p for p in data["doc_paths"]]

        managers = get_analysis_managers()
        inconsistencies = managers["cross_ref"].extract_inconsistencies(doc_paths)

        return (
            jsonify(
                {
                    "count": len(inconsistencies),
                    "inconsistencies": [i.to_dict() for i in inconsistencies],
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"Error in find_inconsistencies: {e}")
        return jsonify({"error": str(e)}), 500


@analysis_bp.route("/cross-reference/gaps", methods=["POST"])
def find_gaps():
    """
    Busca gaps entre documentación teórica y configuración real.

    Payload:
    {
        "theory_doc": "docs/network_manual.md",
        "config_file": "config/llm_models.json"  // Use a valid JSON config file
    }
    """
    try:
        data = request.get_json()

        if not data or "theory_doc" not in data:
            return jsonify({"error": "Missing theory_doc"}), 400

        project_root = current_app.config.get("ollash_root_dir", Path.cwd())
        theory_doc = project_root / data["theory_doc"]
        
        # Default to llm_models.json if not specified
        config_file_rel = data.get("config_file", "backend/config/llm_models.json")
        config_file = project_root / config_file_rel

        managers = get_analysis_managers()
        gaps = managers["cross_ref"].find_gaps_theory_vs_practice(theory_doc, config_file)

        return jsonify(gaps), 200

    except Exception as e:
        current_app.logger.error(f"Error in find_gaps: {e}")
        return jsonify({"error": str(e)}), 500


# ============ Knowledge Graph Endpoints ============


@analysis_bp.route("/knowledge-graph/build", methods=["POST"])
def build_knowledge_graph():
    """
    Construye el grafo de conocimiento desde documentación.

    Payload:
    {
        "doc_paths": ["docs/README.md", "docs/ARCHITECTURE.md"],  // opcional
        "rebuild": false  // si true, reconstruye desde cero
    }
    """
    try:
        data = request.get_json() or {}

        doc_paths = None
        if "doc_paths" in data:
            project_root = current_app.config.get("ollash_root_dir", Path.cwd())
            doc_paths = [project_root / p for p in data["doc_paths"]]

        managers = get_analysis_managers()
        stats = managers["knowledge_graph"].build_from_documentation(doc_paths)

        return jsonify({"status": "success", "stats": stats}), 200

    except Exception as e:
        current_app.logger.error(f"Error building knowledge graph: {e}")
        return jsonify({"error": str(e)}), 500


@analysis_bp.route("/knowledge-graph/connections/<term>", methods=["GET"])
def get_concept_connections(term):
    """Obtiene todas las conexiones de un concepto."""
    try:
        max_depth = request.args.get("max_depth", 2, type=int)

        managers = get_analysis_managers()
        connections = managers["knowledge_graph"].get_concept_connections(term, max_depth)

        return jsonify(connections), 200

    except Exception as e:
        current_app.logger.error(f"Error getting connections: {e}")
        return jsonify({"error": str(e)}), 500


@analysis_bp.route("/knowledge-graph/paths", methods=["POST"])
def find_knowledge_paths():
    """
    Busca caminos entre dos términos en el grafo.

    Payload:
    {
        "start_term": "API",
        "end_term": "REST"
    }
    """
    try:
        data = request.get_json()

        if not data or "start_term" not in data or "end_term" not in data:
            return jsonify({"error": "Missing start_term or end_term"}), 400

        start_term = data["start_term"]
        end_term = data["end_term"]

        managers = get_analysis_managers()
        paths = managers["knowledge_graph"].find_knowledge_paths(start_term, end_term)

        return (
            jsonify(
                {
                    "start_term": start_term,
                    "end_term": end_term,
                    "path_count": len(paths),
                    "paths": paths,
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"Error finding paths: {e}")
        return jsonify({"error": str(e)}), 500


@analysis_bp.route("/knowledge-graph/index", methods=["GET"])
def get_thematic_index():
    """Obtiene el índice temático del grafo de conocimiento."""
    try:
        managers = get_analysis_managers()
        index = managers["knowledge_graph"].generate_thematic_index()

        return jsonify(index), 200

    except Exception as e:
        current_app.logger.error(f"Error getting thematic index: {e}")
        return jsonify({"error": str(e)}), 500


@analysis_bp.route("/knowledge-graph/export/mermaid", methods=["GET"])
def export_mermaid_diagram():
    """Exporta el grafo en formato Mermaid."""
    try:
        managers = get_analysis_managers()
        mermaid_code = managers["knowledge_graph"].export_graph_mermaid()

        return jsonify({"format": "mermaid", "diagram": mermaid_code}), 200

    except Exception as e:
        current_app.logger.error(f"Error exporting Mermaid: {e}")
        return jsonify({"error": str(e)}), 500


# ============ Decision Context Endpoints ============


@analysis_bp.route("/decisions/record", methods=["POST"])
def record_decision():
    """
    Registra una nueva decisión.

    Payload:
    {
        "decision": "Use Cosmos DB for chat history",
        "reasoning": "Provides global distribution and low latency",
        "category": "architecture",
        "context": {"problem": "Need scalable storage for multi-region"},
        "project": "project_name",
        "tags": ["database", "scalability"]
    }
    """
    try:
        data = request.get_json()

        required = ["decision", "reasoning", "category", "context"]
        if not data or not all(k in data for k in required):
            return jsonify({"error": f"Missing required fields: {required}"}), 400

        managers = get_analysis_managers()
        decision_id = managers["decision_context"].record_decision(
            decision=data["decision"],
            reasoning=data["reasoning"],
            category=data["category"],
            context=data["context"],
            project=data.get("project"),
            tags=data.get("tags"),
        )

        return jsonify({"status": "success", "decision_id": decision_id}), 201

    except Exception as e:
        current_app.logger.error(f"Error recording decision: {e}")
        return jsonify({"error": str(e)}), 500


@analysis_bp.route("/decisions/similar", methods=["POST"])
def find_similar_decisions():
    """
    Busca decisiones similares.

    Payload:
    {
        "problem": "Need to improve database performance",
        "category": "performance",
        "project": "project_name",
        "max_results": 5
    }
    """
    try:
        data = request.get_json()

        if not data or "problem" not in data:
            return jsonify({"error": "Missing problem"}), 400

        managers = get_analysis_managers()
        similar = managers["decision_context"].find_similar_decisions(
            problem=data["problem"],
            category=data.get("category"),
            project=data.get("project"),
            max_results=data.get("max_results", 5),
        )

        return (
            jsonify(
                {
                    "problem": data["problem"],
                    "similar_decisions": [d.to_dict() for d in similar],
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"Error finding similar decisions: {e}")
        return jsonify({"error": str(e)}), 500


@analysis_bp.route("/decisions/suggestions", methods=["POST"])
def get_suggestions():
    """
    Obtiene sugerencias basadas en historial de decisiones.

    Payload:
    {
        "question": "How should we handle high database load?",
        "category": "architecture"
    }
    """
    try:
        data = request.get_json()

        if not data or "question" not in data:
            return jsonify({"error": "Missing question"}), 400

        managers = get_analysis_managers()
        suggestions = managers["decision_context"].suggest_based_on_history(
            question=data["question"], category=data.get("category")
        )

        return jsonify({"question": data["question"], "suggestions": suggestions}), 200

    except Exception as e:
        current_app.logger.error(f"Error getting suggestions: {e}")
        return jsonify({"error": str(e)}), 500


@analysis_bp.route("/decisions/outcome/<decision_id>", methods=["PUT"])
def update_decision_outcome(decision_id):
    """
    Actualiza el outcome de una decisión.

    Payload:
    {
        "success": true,
        "lesson": "Cosmos DB scaled well, but costs higher than expected",
        "metrics": {"query_latency_ms": 45, "cost_per_month": 1200}
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Missing outcome data"}), 400

        managers = get_analysis_managers()
        success = managers["decision_context"].update_outcome(decision_id, data)

        if not success:
            return jsonify({"error": "Decision not found"}), 404

        return jsonify({"status": "success", "decision_id": decision_id}), 200

    except Exception as e:
        current_app.logger.error(f"Error updating outcome: {e}")
        return jsonify({"error": str(e)}), 500


@analysis_bp.route("/decisions/project/<project_name>", methods=["GET"])
def get_project_context(project_name):
    """Obtiene el contexto completo de un proyecto."""
    try:
        managers = get_analysis_managers()
        context = managers["decision_context"].get_project_context(project_name)

        return jsonify(context), 200

    except Exception as e:
        current_app.logger.error(f"Error getting project context: {e}")
        return jsonify({"error": str(e)}), 500


@analysis_bp.route("/decisions/statistics", methods=["GET"])
def get_decision_statistics():
    """Obtiene estadísticas del historial de decisiones."""
    try:
        managers = get_analysis_managers()
        stats = managers["decision_context"].get_statistics()

        return jsonify(stats), 200

    except Exception as e:
        current_app.logger.error(f"Error getting statistics: {e}")
        return jsonify({"error": str(e)}), 500


@analysis_bp.route("/decisions/all", methods=["GET"])
def list_all_decisions():
    """Lista todas las decisiones."""
    try:
        project = request.args.get("project")

        managers = get_analysis_managers()
        decisions = managers["decision_context"].get_all_decisions(project)

        return (
            jsonify(
                {
                    "count": len(decisions),
                    "project": project,
                    "decisions": [d.to_dict() for d in decisions],
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"Error listing decisions: {e}")
        return jsonify({"error": str(e)}), 500


def init_app(app):
    """Inicializa el blueprint con la app."""
    app.logger.info("✓ Analysis blueprint registered")
