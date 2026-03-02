"""
Alerts router — migrated from alerts_bp.py.

SSE streaming: uses FastAPI StreamingResponse instead of Flask's
stream_with_context(). EventPublisher subscription pattern preserved.
"""

import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from backend.api.deps import get_event_publisher, get_alert_manager

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


async def _alert_event_generator(event_publisher) -> AsyncIterator[str]:
    """
    Async SSE generator — subscribes to the EventPublisher and yields
    Server-Sent Events. Sends heartbeats every 30 s to keep connection alive.
    """
    event_queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def _callback(event_type: str, event_data: dict) -> None:
        # Called from the sync EventPublisher; bridge into the asyncio queue
        loop.call_soon_threadsafe(event_queue.put_nowait, (event_type, event_data))

    event_publisher.subscribe("ui_alert", _callback)
    try:
        while True:
            try:
                event_type, event_data = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                data = json.dumps(event_data)
                yield f"event: {event_type}\ndata: {data}\n\n"
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
    finally:
        event_publisher.unsubscribe("ui_alert", _callback)


@router.get("/stream")
async def stream_alerts(event_publisher=Depends(get_event_publisher)):
    """SSE endpoint for real-time alert events."""
    return StreamingResponse(
        _alert_event_generator(event_publisher),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("")
async def get_alerts(alert_manager=Depends(get_alert_manager)):
    """Return all currently active alerts."""
    alerts = alert_manager.get_active_alerts()
    return {"ok": True, "alerts": alerts, "total": len(alerts)}


@router.post("/dismiss/{alert_id}")
async def dismiss_alert(alert_id: str, alert_manager=Depends(get_alert_manager)):
    alert_manager.dismiss_alert(alert_id)
    return {"ok": True}
