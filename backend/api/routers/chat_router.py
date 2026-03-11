"""
Chat router — migrated from chat_bp.py.

Long-running chat tasks run as background asyncio tasks.
SSE uses StreamingResponse with async generator.
"""

import asyncio
from typing import AsyncIterator, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


router = APIRouter(tags=["chat"])

# Module-level session manager (initialized on first request via state)
_session_manager = None


def _get_session_manager(request: Request):
    """Lazily initialize the session manager from app state."""
    global _session_manager
    if _session_manager is None:
        from backend.services.chat_session_manager import ChatSessionManager

        _session_manager = ChatSessionManager(
            request.app.state.ollash_root_dir,
            request.app.state.event_publisher,
        )
    return _session_manager


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    model: Optional[str] = None
    mode: Optional[str] = "default"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/api/chat")
async def send_chat(
    payload: ChatRequest,
    background_tasks: BackgroundTasks,
    request: Request,
):
    """Initiate a chat turn. Processing runs as a background task."""
    mgr = _get_session_manager(request)

    session_id = payload.session_id
    if not session_id or mgr.get_session(session_id) is None:
        session_id = mgr.create_session(
            model=payload.model,
            mode=payload.mode,
        )

    background_tasks.add_task(mgr.send_message, session_id, payload.message)
    return {"status": "started", "session_id": session_id}


@router.get("/api/chat/stream/{session_id}")
async def stream_chat(session_id: str, request: Request):
    """SSE stream for incremental chat output."""
    mgr = _get_session_manager(request)
    session = mgr.get_session(session_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    async def _event_gen() -> AsyncIterator[str]:
        # iter_events() is a sync generator in the bridge; wrap with asyncio
        loop = asyncio.get_event_loop()
        bridge = session.bridge
        it = iter(bridge.iter_events())

        def _get_next(iterator):
            try:
                return next(iterator)
            except StopIteration:
                return None

        while True:
            chunk = await loop.run_in_executor(None, _get_next, it)
            if chunk is None:
                break
            yield chunk

    return StreamingResponse(
        _event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/api/chat/sessions")
async def list_sessions(background_tasks: BackgroundTasks, request: Request):
    mgr = _get_session_manager(request)
    background_tasks.add_task(mgr.delete_empty_sessions)
    sessions = mgr.list_sessions()
    return {"sessions": [dict(s) for s in sessions]}


@router.delete("/api/chat/sessions")
async def delete_all_sessions(request: Request):
    """Delete all chat sessions and their history."""
    mgr = _get_session_manager(request)
    mgr.delete_all_sessions()
    return {"status": "deleted_all"}


@router.delete("/api/chat/sessions/{session_id}")
async def delete_session(session_id: str, request: Request):
    mgr = _get_session_manager(request)
    mgr.delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


@router.get("/api/chat/sessions/{session_id}/history")
async def get_session_history(session_id: str, request: Request):
    mgr = _get_session_manager(request)
    history = mgr.get_session_history(session_id)
    return {"session_id": session_id, "history": [dict(row) for row in history]}
