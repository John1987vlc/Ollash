from flask import Blueprint, jsonify, request, render_template
from werkzeug.utils import secure_filename
from backend.core.containers import main_container

knowledge_bp = Blueprint("knowledge", __name__)


@knowledge_bp.route("/knowledge")
def knowledge_page():
    return render_template("pages/knowledge.html")


def get_doc_manager():
    return main_container.core.documentation_manager()


@knowledge_bp.route("/api/knowledge/documents", methods=["GET"])
def list_documents():
    """Returns a list of documents indexed in the documentation_store collection."""
    try:
        mgr = get_doc_manager()
        # ChromaDB collections have a .get() method to list IDs and metadata
        docs = mgr.documentation_collection.get()
        # Format for UI
        results = []
        if docs and "ids" in docs:
            for i in range(len(docs["ids"])):
                meta = docs["metadatas"][i] if docs["metadatas"] else {}
                results.append(
                    {
                        "id": docs["ids"][i],
                        "filename": meta.get("filename", "Unknown"),
                        "source": meta.get("source", "Manual Upload"),
                        "timestamp": meta.get("timestamp", ""),
                    }
                )
        return jsonify({"documents": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/api/knowledge/upload", methods=["POST"])
def upload_document():
    """Uploads a document, saves it to knowledge_workspace/ingest and indexes it."""
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    filename = secure_filename(file.filename)
    root = main_container.core.ollash_root_dir()
    ingest_dir = root / "knowledge_workspace" / "ingest"
    ingest_dir.mkdir(parents=True, exist_ok=True)

    file_path = ingest_dir / filename
    file.save(str(file_path))

    try:
        mgr = get_doc_manager()
        # DocumentationManager has index_document_file method
        success = mgr.index_document_file(file_path)
        if success:
            return jsonify({"status": "success", "filename": filename})
        else:
            return jsonify({"error": "Failed to index document"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/api/knowledge/documents/<doc_id>", methods=["DELETE"])
def delete_document(doc_id):
    """Deletes a document from the vector store."""
    try:
        mgr = get_doc_manager()
        mgr.documentation_collection.delete(ids=[doc_id])
        return jsonify({"status": "deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/api/knowledge/errors", methods=["GET"])
def get_error_knowledge():
    """Returns statistics and patterns from the Error Knowledge Base."""
    try:
        ekb = main_container.core.error_knowledge_base()
        stats = ekb.get_error_statistics()
        patterns = [p.to_dict() for p in ekb.patterns.values()]
        return jsonify({"statistics": stats, "patterns": patterns})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/api/knowledge/episodes", methods=["GET"])
def get_episodic_memory():
    """Returns statistics and recent episodes from Episodic Memory."""
    try:
        em = main_container.core.episodic_memory()
        stats = em.get_statistics()

        # Get all episodes from DB
        import sqlite3
        with sqlite3.connect(str(em._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM episodes ORDER BY timestamp DESC LIMIT 50").fetchall()
            episodes = [dict(row) for row in rows]

            # Get decisions too
            decision_rows = conn.execute("SELECT * FROM decisions ORDER BY timestamp DESC LIMIT 50").fetchall()
            decisions = [dict(row) for row in decision_rows]

        return jsonify({
            "statistics": stats,
            "episodes": episodes,
            "decisions": decisions
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
