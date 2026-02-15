import time
from typing import Dict, Any, Optional
from backend.utils.core.agent_logger import AgentLogger # Use AgentLogger for structured logging
from backend.utils.core.structured_logger import get_correlation_id


class ToolSpanManager:
    """
    Manages the lifecycle of tool execution spans for structured logging.
    Records start/end times, success/failure, and relevant metadata.
    """
    def __init__(self, logger: AgentLogger):
        self._logger = logger
        self._active_spans: Dict[str, Dict[str, Any]] = {} # tool_call_id -> span_data

    def start_span(self, tool_name: str, tool_args: Dict[str, Any], tool_call_id: Optional[str] = None) -> str:
        """
        Starts a new tool execution span and records its beginning.
        Generates a tool_call_id if not provided.
        """
        if tool_call_id is None:
            tool_call_id = f"{tool_name}-{time.monotonic()}" # Simple unique ID for now

        start_time = time.monotonic()
        span_data = {
            "tool_name": tool_name,
            "tool_args": tool_args,
            "start_time": start_time,
            "correlation_id": get_correlation_id(), # Inherit correlation ID
            "status": "in_progress",
        }
        self._active_spans[tool_call_id] = span_data

        self._logger.info(
            f"Tool Execution Started: {tool_name}",
            extra={
                "event_type": "tool_span_start",
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "tool_args": tool_args,
            }
        )
        return tool_call_id

    def end_span(self, tool_call_id: str, success: bool, result: Any, error: Optional[str] = None):
        """
        Ends an active tool execution span and records its completion status.
        """
        span_data = self._active_spans.pop(tool_call_id, None)
        if span_data is None:
            self._logger.warning(f"Attempted to end non-existent tool span: {tool_call_id}")
            return

        end_time = time.monotonic()
        latency = end_time - span_data["start_time"]

        span_data.update({
            "end_time": end_time,
            "latency_ms": latency * 1000,
            "status": "success" if success else "failed",
            "result_preview": str(result)[:500], # Preview of result
            "error_message": error,
        })

        self._logger.info(
            f"Tool Execution Ended: {span_data['tool_name']} - {span_data['status'].upper()}",
            extra={
                "event_type": "tool_span_end",
                "tool_call_id": tool_call_id,
                "tool_name": span_data['tool_name'],
                "latency_ms": span_data['latency_ms'],
                "status": span_data['status'],
                "error_message": error,
                "result_hash": hash(str(result)) # Hash of result to avoid logging large objects
            }
        )
