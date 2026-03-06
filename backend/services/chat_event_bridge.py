import json
import queue
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from backend.utils.core.system.event_publisher import EventPublisher


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

    def __init__(self, event_publisher: EventPublisher):
        self.event_queue: queue.Queue[ChatEvent] = queue.Queue()
        self._closed = False
        self.event_publisher = event_publisher  # Store the event publisher

        # Subscribe to all relevant event types from the EventPublisher
        self.event_publisher.subscribe("phase_start", self.push_event)
        self.event_publisher.subscribe("phase_complete", self.push_event)
        self.event_publisher.subscribe("tool_start", self.push_event)
        self.event_publisher.subscribe("tool_output", self.push_event)
        self.event_publisher.subscribe("tool_end", self.push_event)
        self.event_publisher.subscribe("project_complete", self.push_event)
        self.event_publisher.subscribe("execution_plan_initialized", self.push_event)
        self.event_publisher.subscribe("agent_board_update", self.push_event)
        self.event_publisher.subscribe("iteration_start", self.push_event)
        self.event_publisher.subscribe("iteration_end", self.push_event)
        self.event_publisher.subscribe("error", self.push_event)
        self.event_publisher.subscribe("info", self.push_event)
        self.event_publisher.subscribe("warning", self.push_event)
        self.event_publisher.subscribe("debug", self.push_event)
        # Domain agent / multiagent events
        self.event_publisher.subscribe("domain_orchestration_started", self.push_event)
        self.event_publisher.subscribe("domain_orchestration_completed", self.push_event)
        self.event_publisher.subscribe("task_status_changed", self.push_event)
        self.event_publisher.subscribe("blackboard_updated", self.push_event)
        self.event_publisher.subscribe("task_remediation_queued", self.push_event)
        self.event_publisher.subscribe("architect_planning_started", self.push_event)
        self.event_publisher.subscribe("architect_planning_completed", self.push_event)
        self.event_publisher.subscribe("file_generated", self.push_event)
        # P1 — HITL
        self.event_publisher.subscribe("hil_request", self.push_event)
        self.event_publisher.subscribe("hil_response", self.push_event)
        self.event_publisher.subscribe("clarification_request", self.push_event)
        # P4 — Streaming token chunks
        self.event_publisher.subscribe("blackboard_stream_chunk", self.push_event)
        self.event_publisher.subscribe("token", self.push_event)
        self.event_publisher.subscribe("thinking", self.push_event)
        # P5 — Budget circuit breaker
        self.event_publisher.subscribe("budget_exceeded", self.push_event)
        # P6 — Git auto-commit
        self.event_publisher.subscribe("file_committed", self.push_event)
        # P8 — Debate nodes
        self.event_publisher.subscribe("debate_round_completed", self.push_event)
        self.event_publisher.subscribe("debate_consensus_reached", self.push_event)
        # P3 — Sandbox linter audit
        self.event_publisher.subscribe("audit_sandbox_result", self.push_event)
        # P9 — Tool belt
        self.event_publisher.subscribe("tool_execution_started", self.push_event)
        self.event_publisher.subscribe("tool_execution_completed", self.push_event)
        # Feature 4 — Chaos engineering fault injection
        self.event_publisher.subscribe("chaos_fault_injected", self.push_event)
        # Feature 6 — Context saturation alerts
        self.event_publisher.subscribe("context_saturation_alert", self.push_event)

    def push_event(self, event_type: str, event_data: Optional[Dict[str, Any]] = None):
        """Push an event onto the queue (called from the agent thread)."""
        if self._closed:
            return
        self.event_queue.put(ChatEvent(event_type=event_type, data=event_data or {}))

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

            # Handle non-serializable data (like coroutines) to avoid 500 errors
            sanitized_data = {}
            for k, v in event.data.items():
                if hasattr(v, "__await__") or hasattr(v, "cr_code"):  # Check if it's a coroutine
                    sanitized_data[k] = f"[Pending Coroutine: {getattr(v, '__name__', 'unknown')}]"
                else:
                    sanitized_data[k] = v

            try:
                # F33: Ensure event_type (as 'type') is the final word, avoiding collision with data
                payload_dict = {**sanitized_data, "type": event.event_type}
                payload = json.dumps(payload_dict)
                yield f"data: {payload}\n\n"
            except Exception as e:
                # Fallback for complex objects that still fail
                yield f'data: {{"type": "error", "message": "Serialization error: {str(e)}"}}\n\n'

            if event.event_type == "stream_end":
                break


    def close(self):
        """Signal end of stream."""
        if not self._closed:
            self._closed = True
            # Put directly on queue — push_event() would bail because _closed is True.
            self.event_queue.put(ChatEvent(event_type="stream_end"))
