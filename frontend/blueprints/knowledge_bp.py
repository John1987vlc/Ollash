from flask import Blueprint, jsonify, request, current_app, render_template
from werkzeug.utils import secure_filename
from backend.core.containers import main_container
from backend.utils.core.io.documentation_manager import DocumentationManager

knowledge_bp = Blueprint("knowledge", __name__)


@knowledge_bp.route("/knowledge")
def knowledge_page():
    return render_template("pages/knowledge.html")


_doc_manager: DocumentationManager = None


def get_doc_manager():
    global _doc_manager
    if _doc_manager is None:
        root = main_container.core.ollash_root_dir()
        config = current_app.config.get("config", {})
        _doc_manager = DocumentationManager(config, root)
    return _doc_manager


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
