import json
import queue
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ChatEvent:
    """A structured event pushed from DefaultAgent to the SSE stream."""
    event_type: str  # iteration, tool_call, tool_result, final_answer, error, stream_end
    data: Dict[str, Any] = field(default_factory=dict)


class ChatEventBridge:
    """Thread-safe bridge between DefaultAgent.chat() and an SSE endpoint.

    The agent thread pushes events via push_event(); the Flask SSE
    generator reads them via iter_events().
    """

    def __init__(self):
        self.event_queue: queue.Queue[ChatEvent] = queue.Queue()
        self._closed = False

    def push_event(self, event_type: str, data: Optional[Dict[str, Any]] = None):
        """Push an event onto the queue (called from the agent thread)."""
        if self._closed:
            return
        self.event_queue.put(ChatEvent(event_type=event_type, data=data or {}))

    def iter_events(self, timeout: float = 0.5):
        """Yield SSE-formatted strings. Blocks up to *timeout* seconds per poll.

        Stops when a ``stream_end`` event is received.
        """
        while True:
            try:
                event = self.event_queue.get(timeout=timeout)
            except queue.Empty:
                # Send a keep-alive comment to prevent connection timeout
                yield ": keepalive\n\n"
                continue

            payload = json.dumps({"type": event.event_type, **event.data})
            yield f"data: {payload}\n\n"

            if event.event_type == "stream_end":
                break

    def close(self):
        """Signal end of stream."""
        if not self._closed:
            self._closed = True
            self.push_event("stream_end")
