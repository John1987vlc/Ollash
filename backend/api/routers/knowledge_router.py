"""Knowledge router — document upload, chunking, semantic search, error KB, episodic memory."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

_CHUNK_SIZE = 800
_CHUNK_OVERLAP = 80


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _chunk_text(text: str, chunk_size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> list[str]:
    """Split *text* into overlapping windows."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + chunk_size])
        start += chunk_size - overlap
        if start >= len(text):
            break
    return chunks or [text]


def _get_collection():
    """Return (SQLiteVectorCollection, OllamaClient) from the DI container."""
    from backend.core.containers import main_container

    mgr = main_container.core.documentation_manager()
    return mgr.documentation_collection, mgr.embedding_client


def _list_all_rows(collection) -> list[dict]:
    """Fetch every row from the collection."""
    with sqlite3.connect(collection._db_path) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(f"SELECT id, metadata, added_at FROM {collection._table} ORDER BY added_at DESC").fetchall()

    result = []
    for row in rows:
        try:
            meta = json.loads(row["metadata"])
        except Exception:
            meta = {}
        result.append(
            {
                "id": row["id"],
                "filename": meta.get("filename", "Unknown"),
                "source": meta.get("source", "Manual Upload"),
                "timestamp": meta.get("timestamp", ""),
                "chunk_index": meta.get("chunk_index", 0),
                "doc_id": meta.get("doc_id", row["id"]),
            }
        )
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/")
async def knowledge_index():
    return {"status": "ok", "endpoints": ["/documents", "/upload", "/search", "/errors", "/episodes"]}


@router.get("/documents")
async def list_documents():
    """List unique documents indexed in the knowledge store (deduplicated by doc_id)."""
    try:
        collection, _ = _get_collection()
        rows = _list_all_rows(collection)
        seen: dict[str, dict] = {}
        for row in rows:
            doc_id = row["doc_id"]
            if doc_id not in seen:
                seen[doc_id] = {
                    "id": doc_id,
                    "filename": row["filename"],
                    "source": row["source"],
                    "timestamp": row["timestamp"],
                }
        return {"documents": list(seen.values()), "total": len(seen)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a document — chunk it, embed each chunk, store in the vector collection."""
    raw = await file.read()

    text = None
    for enc in ("utf-8", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        raise HTTPException(status_code=400, detail="Could not decode file as text")
    if not text.strip():
        raise HTTPException(status_code=400, detail="File is empty")

    ingest_dir = Path(".ollash") / "knowledge_workspace" / "ingest"
    ingest_dir.mkdir(parents=True, exist_ok=True)
    (ingest_dir / (file.filename or "upload.txt")).write_bytes(raw)

    collection, embedding_client = _get_collection()
    doc_id = hashlib.md5((file.filename or "upload").encode()).hexdigest()
    chunks = _chunk_text(text)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []
    embeddings: list[list[float]] = []

    for i, chunk in enumerate(chunks):
        ids.append(f"{doc_id}_c{i}")
        documents.append(chunk)
        metadatas.append(
            {
                "filename": file.filename,
                "source": "Manual Upload",
                "timestamp": ts,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "doc_id": doc_id,
            }
        )
        embeddings.append(embedding_client.get_embedding(chunk, max_chars=512))

    collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
    return {"status": "success", "filename": file.filename, "doc_id": doc_id, "chunks": len(chunks)}


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete all chunks of a document from the vector store."""
    try:
        collection, _ = _get_collection()
        rows = _list_all_rows(collection)
        chunk_ids = [r["id"] for r in rows if r["doc_id"] == doc_id]
        if chunk_ids:
            collection.delete(ids=chunk_ids)
        return {"status": "deleted", "chunks_removed": len(chunk_ids)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_knowledge(
    q: str = Query(..., description="Search query"),
    n: int = Query(10, ge=1, le=50),
):
    """Semantic search using cosine similarity on stored embeddings."""
    try:
        collection, embedding_client = _get_collection()
        query_emb = embedding_client.get_embedding(q, max_chars=512)
        results = collection.query(query_embeddings=[query_emb], n_results=n)
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]
        hits = [
            {
                "id": ids[i],
                "text": docs[i][:400],
                "score": round(dists[i], 4),
                "filename": (metas[i] or {}).get("filename", ""),
                "chunk_index": (metas[i] or {}).get("chunk_index", 0),
            }
            for i in range(len(ids))
        ]
        return {"query": q, "hits": hits, "count": len(hits)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/errors")
async def get_error_knowledge():
    """Statistics and patterns from the Error Knowledge Base."""
    try:
        from backend.core.containers import main_container

        ekb = main_container.core.memory.error_knowledge_base()
        stats = ekb.get_error_statistics()
        patterns = [p.to_dict() for p in ekb.patterns.values()]
        return {"statistics": stats, "patterns": patterns}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/episodes")
async def get_episodic_memory():
    """Statistics and recent episodes from Episodic Memory."""
    try:
        from backend.core.containers import main_container

        em = main_container.core.memory.episodic_memory()
        stats = em.get_statistics()
        with sqlite3.connect(str(em._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            episodes = [
                dict(r) for r in conn.execute("SELECT * FROM episodes ORDER BY timestamp DESC LIMIT 50").fetchall()
            ]
            decisions = [
                dict(r) for r in conn.execute("SELECT * FROM decisions ORDER BY timestamp DESC LIMIT 50").fetchall()
            ]
        return {"statistics": stats, "episodes": episodes, "decisions": decisions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
