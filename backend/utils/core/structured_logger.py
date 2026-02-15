import json
import logging
import logging.handlers
import threading  # For thread-local correlation ID
from pathlib import Path
from typing import Any, Dict, List, Optional

# Thread-local storage for correlation ID
_correlation_id_storage = threading.local()


def set_correlation_id(correlation_id: str):
    _correlation_id_storage.id = correlation_id


def get_correlation_id() -> Optional[str]:
    return getattr(_correlation_id_storage, "id", None)


class JsonFormatter(logging.Formatter):
    """
    A logging formatter that outputs records as JSON strings.
    Automatically includes a 'correlation_id' if available in thread-local storage.
    """

    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "file": f"{record.filename}:{record.lineno}",
            "func": record.funcName,
        }

        # Add correlation ID if present
        correlation_id = get_correlation_id()
        if correlation_id:
            log_record["correlation_id"] = correlation_id

        # Add extra attributes
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "args",
                "asctime",
                "correlation_id",
            ]:  # Exclude standard and already included
                if key.startswith("_"):  # Skip internal attributes
                    continue
                try:
                    json.dumps(value)  # Check if serializable
                    log_record[key] = value
                except TypeError:
                    log_record[key] = repr(value)  # Fallback to string representation

        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            log_record["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(log_record)


class StructuredLogger:
    """
    A wrapper around Python's logging module configured to output structured JSON logs
    with automatic file rotation.
    """

    def __init__(
        self,
        log_file_path: Path,
        logger_name: str = "ollash",
        log_level: str = "INFO",
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ):
        self._logger = logging.getLogger(logger_name)
        self._logger.setLevel(log_level.upper())
        self._logger.propagate = False  # Prevent logs from going to root logger

        # Ensure log directory exists
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(JsonFormatter())
        self._logger.addHandler(file_handler)

        # Console handler for development (optional, can be removed in production)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter("%(levelname)s - %(name)s - %(message)s")
        )
        self._logger.addHandler(console_handler)

    def get_logger(self) -> logging.Logger:
        return self._logger

    def debug(self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self._logger.debug(msg, extra=extra, **kwargs)

    def info(self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self._logger.info(msg, extra=extra, **kwargs)

    def warning(self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self._logger.warning(msg, extra=extra, **kwargs)

    def error(self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self._logger.error(msg, extra=extra, **kwargs)

    def critical(self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self._logger.critical(msg, extra=extra, **kwargs)

    def exception(self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self._logger.exception(msg, extra=extra, **kwargs)

    # --- Specific structured logging methods ---
    def event(self, event_name: str, event_data: Dict[str, Any]):
        """Logs a generic structured event."""
        self._logger.info(event_name, extra={"event": event_name, "data": event_data})

    def tool_call(self, tool_name: str, args: Dict[str, Any]):
        """Logs a tool call event."""
        self._logger.info(
            f"Tool Call: {tool_name}",
            extra={"type": "tool_call", "tool_name": tool_name, "args": args},
        )

    def tool_result(self, tool_name: str, result: Any, success: bool):
        """Logs a tool result event."""
        self._logger.info(
            f"Tool Result: {tool_name} {'SUCCESS' if success else 'FAILURE'}",
            extra={
                "type": "tool_result",
                "tool_name": tool_name,
                "result": result,
                "success": success,
            },
        )

    def llm_request(self, model: str, prompt_len: int, messages: List[Dict]):
        """Logs an LLM API request."""
        self._logger.info(
            f"LLM Request to {model}",
            extra={
                "type": "llm_request",
                "model": model,
                "prompt_length": prompt_len,
                "messages_hash": hash(json.dumps(messages)),
            },
        )  # Hash to avoid logging huge messages directly

    def llm_response(
        self,
        model: str,
        response_data: Dict,
        usage: Dict,
        latency: float,
        success: bool,
    ):
        """Logs an LLM API response."""
        self._logger.info(
            f"LLM Response from {model}",
            extra={
                "type": "llm_response",
                "model": model,
                "success": success,
                "latency_ms": latency * 1000,
                "usage": usage,
                "response_hash": hash(json.dumps(response_data)),
            },
        )
