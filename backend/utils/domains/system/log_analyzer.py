"""
Log Analyzer for the Ollash Agent Framework.

This module provides a class to analyze log files for errors and
anomalies.
"""

from pathlib import Path
from typing import Dict, Any

from backend.utils.core.agent_logger import AgentLogger

class LogAnalyzer:
    """Analyzes log files for errors and anomalies."""

    def __init__(self, logger: AgentLogger):
        """
        Initializes the LogAnalyzer.

        Args:
            logger: The logger instance.
        """
        self.logger = logger

    def analyze_log_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Analyzes a log file for errors and anomalies.

        Args:
            file_path: The path to the log file.

        Returns:
            A dictionary with analysis results.
        """
        if not file_path.exists():
            return {"status": "error", "message": f"Log file not found: {file_path}"}

        results = {
            "error_count": 0,
            "warning_count": 0,
            "errors": [],
            "warnings": [],
        }

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "ERROR" in line:
                        results["error_count"] += 1
                        results["errors"].append(line.strip())
                    elif "WARNING" in line:
                        results["warning_count"] += 1
                        results["warnings"].append(line.strip())

            self.logger.info(f"Analyzed log file {file_path}: {results['error_count']} errors, {results['warning_count']} warnings.")
            return {"status": "ok", "results": results}
        except Exception as e:
            self.logger.error(f"Failed to analyze log file {file_path}: {e}")
            return {"status": "error", "message": str(e)}

