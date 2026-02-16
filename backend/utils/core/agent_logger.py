import logging
import traceback
from typing import Any, Dict, Optional

from colorama import (  # Still used for console output in chat_mode, not for file logs
    Fore,
    Style,
    init,
)

from backend.utils.core.structured_logger import StructuredLogger

# Initialize colorama for Windows support
init(autoreset=True)


class AgentLogger:
    """
    A wrapper around StructuredLogger to provide agent-specific logging methods
    and maintain compatibility with existing agent code.
    It delegates to a StructuredLogger instance provided at initialization.
    """

    def __init__(self, structured_logger: StructuredLogger, logger_name: str = "OllashAgent"):
        self._logger = structured_logger.get_logger()
        self.name = logger_name  # Store name for specific agent identification if needed

    def _log_to_structured(self, level: int, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        """Helper to log to the underlying StructuredLogger, injecting correlation ID."""
        full_extra = extra if extra is not None else {}
        # StructuredLogger's formatter already injects correlation_id, so no need to do it here again
        self._logger.log(level, msg, extra=full_extra, **kwargs)

    def tool_call(self, tool_name: str, args: Dict):
        """Log tool call with details"""
        console_msg = f"🔧 TOOL CALL: {tool_name}"
        self.info(
            f"{Fore.CYAN}{console_msg}{Style.RESET_ALL}",
            extra={"type": "tool_call", "tool_name": tool_name, "args": args},
        )

    def tool_result(
        self,
        tool_name: str,
        result: Dict,
        success: bool = True,
        latency_ms: Optional[float] = None,
    ):
        """Log tool result"""
        status = "✅ SUCCESS" if success else "❌ FAILED"
        color = Fore.GREEN if success else Fore.RED
        console_msg = f"{status}: {tool_name}"
        extra_data = {
            "type": "tool_result",
            "tool_name": tool_name,
            "result": result,
            "success": success,
        }
        if latency_ms is not None:
            extra_data["latency_ms"] = latency_ms
        self.info(f"{color}{console_msg}{Style.RESET_ALL}", extra=extra_data)

    def api_request(self, messages_count: int, tools_count: int):
        """Log API request"""
        console_msg = f"📡 API REQUEST: {messages_count} messages, {tools_count} tools available"
        self.info(
            f"{Fore.YELLOW}{console_msg}{Style.RESET_ALL}",
            extra={
                "type": "api_request",
                "messages_count": messages_count,
                "tools_count": tools_count,
            },
        )

    def api_response(
        self,
        has_tool_calls: bool,
        tool_count: int = 0,
        latency_ms: Optional[float] = None,
    ):
        """Log API response"""
        if has_tool_calls:
            console_msg = f"📨 API RESPONSE: {tool_count} tool call(s)"
        else:
            console_msg = "📨 API RESPONSE: Final answer"
        extra_data = {
            "type": "api_response",
            "has_tool_calls": has_tool_calls,
            "tool_count": tool_count,
        }
        if latency_ms is not None:
            extra_data["latency_ms"] = latency_ms
        self.info(f"{Fore.YELLOW}{console_msg}{Style.RESET_ALL}", extra=extra_data)

    def error(
        self,
        error_msg: str,
        exception: Optional[Exception] = None,
        extra: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """Log error with full traceback"""
        console_msg = f"{Fore.RED}❌ ERROR: {error_msg}{Style.RESET_ALL}"
        # structured_logger.py's JsonFormatter handles exc_info, so pass it directly.
        self._log_to_structured(logging.ERROR, console_msg, exc_info=exception, extra=extra, **kwargs)
        if exception:
            self._log_to_structured(
                logging.DEBUG,
                traceback.format_exc(),
                extra={"type": "traceback_detail"},
                **kwargs,
            )

    def info(self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        """Log info message"""
        self._log_to_structured(logging.INFO, msg, extra=extra, **kwargs)

    def debug(self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        """Log debug message"""
        self._log_to_structured(logging.DEBUG, msg, extra=extra, **kwargs)

    def warning(self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        """Log warning message"""
        console_msg = f"{Fore.YELLOW}⚠️  {msg}{Style.RESET_ALL}"
        self._log_to_structured(logging.WARNING, console_msg, extra=extra, **kwargs)
