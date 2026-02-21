import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.utils.core.system.db.sqlite_manager import DatabaseManager

# Thread-local storage for correlation ID
_correlation_id_storage = threading.local()


def set_correlation_id(correlation_id: str):
    _correlation_id_storage.id = correlation_id


def get_correlation_id() -> Optional[str]:
    return getattr(_correlation_id_storage, "id", None)


class StructuredLogger:
    """
    A wrapper around Python's logging module configured to output structured logs
    to a SQLite database (logs.db) for better querying and performance.
    """

    def __init__(
        self,
        log_file_path: Path,  # Kept for compatibility but used to derive DB path
        logger_name: str = "ollash",
        log_level: str = "INFO",
    ):
        self._logger = logging.getLogger(logger_name)
        self._logger.setLevel(log_level.upper())
        self._logger.propagate = False

        # Initialize SQLite DB for logs
        # log_file_path is usually .../logs/ollash.log
        # We want .../.ollash/logs.db
        root_dir = log_file_path.parent.parent  # Assuming logs/ is one level deep
        if root_dir.name == "logs":  # Correction if path is direct
            root_dir = root_dir.parent

        db_path = root_dir / ".ollash" / "logs.db"
        self.db = DatabaseManager(db_path)
        self._init_db()

        # Add a console handler for development visibility
        if not self._logger.hasHandlers():
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter("%(levelname)s - %(name)s - %(message)s")
            console_handler.setFormatter(console_formatter)
            self._logger.addHandler(console_handler)

    def _init_db(self):
        """Initialize the logs table."""
        with self.db.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    level TEXT NOT NULL,
                    name TEXT NOT NULL,
                    message TEXT NOT NULL,
                    correlation_id TEXT,
                    file TEXT,
                    func TEXT,
                    extra_data TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)")

    def _write_log(self, level: str, msg: str, record: logging.LogRecord):
        """Write a log entry to the database."""
        extra = {}
        # Collect extra fields
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
            ]:
                if not key.startswith("_"):
                    try:
                        # Ensure serializability
                        json.dumps(value)
                        extra[key] = value
                    except (TypeError, OverflowError):
                        extra[key] = str(value)

        data = {
            "level": level,
            "name": record.name,
            "message": msg,
            "correlation_id": get_correlation_id(),
            "file": f"{record.filename}:{record.lineno}",
            "func": record.funcName,
            "extra_data": json.dumps(extra),
        }

        try:
            # Direct execute for speed, relying on WAL mode
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?" for _ in data])
            self.db.execute(f"INSERT INTO logs ({columns}) VALUES ({placeholders})", tuple(data.values()))
        except Exception as e:
            # Fallback to console if DB fails
            print(f"LOG DB ERROR: {e}")

    # Standard logging methods wrapper
    def log(self, level, msg, *args, **kwargs):
        if self._logger.isEnabledFor(level):
            record = self._logger.makeRecord(self._logger.name, level, "(unknown)", 0, msg, args, None)
            # Apply extra from kwargs manually since we bypass standard handle
            if "extra" in kwargs and kwargs["extra"]:
                for k, v in kwargs["extra"].items():
                    setattr(record, k, v)

            self._logger.handle(record)  # Console output
            self._write_log(logging.getLevelName(level), msg, record)  # DB output

    def debug(self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self.log(logging.DEBUG, msg, extra=extra, **kwargs)

    def info(self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self.log(logging.INFO, msg, extra=extra, **kwargs)

    def warning(self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self.log(logging.WARNING, msg, extra=extra, **kwargs)

    def error(self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self.log(logging.ERROR, msg, extra=extra, **kwargs)

    def critical(self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self.log(logging.CRITICAL, msg, extra=extra, **kwargs)

    def exception(self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        kwargs["exc_info"] = True
        self.log(logging.ERROR, msg, extra=extra, **kwargs)

    def get_logger(self):
        # Return self to intercept calls, or return _logger if we patch it
        # Returning self is safer to enforce _write_log
        return self

    # --- Specific structured logging methods ---
    def event(self, event_name: str, event_data: Dict[str, Any]):
        self.info(event_name, extra={"event": event_name, "data": event_data})

    def tool_call(self, tool_name: str, args: Dict[str, Any]):
        self.info(
            f"Tool Call: {tool_name}",
            extra={"type": "tool_call", "tool_name": tool_name, "args": args},
        )

    def tool_result(self, tool_name: str, result: Any, success: bool):
        self.info(
            f"Tool Result: {tool_name} {'SUCCESS' if success else 'FAILURE'}",
            extra={
                "type": "tool_result",
                "tool_name": tool_name,
                "result": result,
                "success": success,
            },
        )

    def llm_request(self, model: str, prompt_len: int, messages: List[Dict]):
        self.info(
            f"LLM Request to {model}",
            extra={
                "type": "llm_request",
                "model": model,
                "prompt_length": prompt_len,
                "messages_hash": hash(json.dumps(messages)),
            },
        )

    def llm_response(
        self,
        model: str,
        response_data: Dict,
        usage: Dict,
        latency: float,
        success: bool,
    ):
        self.info(
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
