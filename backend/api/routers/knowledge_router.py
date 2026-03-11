"""
knowledge_router - migrated from knowledge_views.py.
Handles knowledge base documents, uploads, and memory statistics.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from backend.core.containers import main_container

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def get_doc_manager():
    return main_container.core.documentation_manager()


@router.get("/documents")
async def list_documents():
    """Returns a list of documents indexed in the documentation_store collection."""
    try:
        mgr = get_doc_manager()
        # ChromaDB collections have a .get() method to list IDs and metadata
        docs = mgr.documentation_collection.get()
        # Format for UI
        results = []
        if docs and "ids" in docs:
            ids = docs.get("ids", [])
            metas = docs.get("metadatas", [])

            for i in range(len(ids)):
                meta = {}
                if metas and i < len(metas) and metas[i]:
                    meta = metas[i]

                results.append(
                    {
                        "id": ids[i],
                        "filename": meta.get("filename", "Unknown"),
                        "source": meta.get("source", "Manual Upload"),
                        "timestamp": meta.get("timestamp", ""),
                    }
                )
        return {"documents": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Uploads a document, saves it to knowledge_workspace/ingest and indexes it."""
    root = main_container.core.ollash_root_dir()
    ingest_dir = root / "knowledge_workspace" / "ingest"
    ingest_dir.mkdir(parents=True, exist_ok=True)

    file_path = ingest_dir / file.filename
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    try:
        mgr = get_doc_manager()
        success = mgr.index_document_file(file_path)
        if success:
            return {"status": "success", "filename": file.filename}
        else:
            raise HTTPException(status_code=500, detail="Failed to index document")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Deletes a document from the vector store."""
    try:
        mgr = get_doc_manager()
        mgr.documentation_collection.delete(ids=[doc_id])
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/errors")
async def get_error_knowledge():
    """Returns statistics and patterns from the Error Knowledge Base."""
    try:
        ekb = main_container.core.memory.error_knowledge_base()
        stats = ekb.get_error_statistics()
        patterns = [p.to_dict() for p in ekb.patterns.values()]
        return {"statistics": stats, "patterns": patterns}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/episodes")
async def get_episodic_memory():
    """Returns statistics and recent episodes from Episodic Memory."""
    try:
        em = main_container.core.memory.episodic_memory()
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

        return {"statistics": stats, "episodes": episodes, "decisions": decisions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def knowledge_index():
    return {"status": "ok", "router": "knowledge"}
