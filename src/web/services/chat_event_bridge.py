import json
import queue
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from src.utils.core.event_publisher import EventPublisher # ADDED IMPORT


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

    def __init__(self, event_publisher: EventPublisher): # MODIFIED
        self.event_queue: queue.Queue[ChatEvent] = queue.Queue()
        self._closed = False
        self.event_publisher = event_publisher # Store the event publisher

        # Subscribe to all relevant event types from the EventPublisher
        self.event_publisher.subscribe("phase_start", self.push_event)
        self.event_publisher.subscribe("phase_complete", self.push_event)
        self.event_publisher.subscribe("tool_start", self.push_event)
        self.event_publisher.subscribe("tool_output", self.push_event)
        self.event_publisher.subscribe("tool_end", self.push_event)
        self.event_publisher.subscribe("project_complete", self.push_event)
        self.event_publisher.subscribe("iteration_start", self.push_event)
        self.event_publisher.subscribe("iteration_end", self.push_event)
        self.event_publisher.subscribe("error", self.push_event)
        self.event_publisher.subscribe("info", self.push_event) # General info messages
        self.event_publisher.subscribe("warning", self.push_event) # General warning messages
        self.event_publisher.subscribe("debug", self.push_event) # General debug messages


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
            # Put directly on queue — push_event() would bail because _closed is True.
            self.event_queue.put(ChatEvent(event_type="stream_end"))
