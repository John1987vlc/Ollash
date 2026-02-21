"""
Model Health Monitor for the Ollash Agent Framework.

This module provides a class to monitor the health of the Ollama models,
including latency, error rates, and availability.
"""

from collections import deque
from typing import Any, Dict

from backend.utils.core.system.agent_logger import AgentLogger


class ModelHealthMonitor:
    """Monitors the health of Ollama models."""

    def __init__(self, logger: AgentLogger, config: Dict[str, Any]):
        """
        Initializes the ModelHealthMonitor.

        Args:
            logger: The logger instance.
            config: The agent's configuration.
        """
        self.logger = logger
        self.config = config.get("model_health_monitor", {})
        self.window_size = self.config.get("window_size", 100)

        self.latencies: Dict[str, deque] = {}
        self.error_rates: Dict[str, deque] = {}
        self.last_checked: Dict[str, float] = {}

    def record_request(self, model_name: str, latency: float, success: bool):
        """
        Records a request to a model.

        Args:
            model_name: The name of the model.
            latency: The latency of the request in seconds.
            success: Whether the request was successful.
        """
        if model_name not in self.latencies:
            self.latencies[model_name] = deque(maxlen=self.window_size)
        if model_name not in self.error_rates:
            self.error_rates[model_name] = deque(maxlen=self.window_size)

        self.latencies[model_name].append(latency)
        self.error_rates[model_name].append(1 if not success else 0)

    def get_health_stats(self, model_name: str) -> Dict[str, Any]:
        """
        Gets the health stats for a model.

        Args:
            model_name: The name of the model.

        Returns:
            A dictionary with health stats.
        """
        if model_name not in self.latencies:
            return {"status": "unknown"}

        avg_latency = sum(self.latencies[model_name]) / len(self.latencies[model_name])
        error_rate = sum(self.error_rates[model_name]) / len(self.error_rates[model_name])

        return {
            "status": "ok",
            "avg_latency": avg_latency,
            "error_rate": error_rate,
            "window_size": len(self.latencies[model_name]),
        }

    def is_model_healthy(self, model_name: str) -> bool:
        """
        Checks if a model is healthy.

        Args:
            model_name: The name of the model.

        Returns:
            True if the model is healthy, False otherwise.
        """
        stats = self.get_health_stats(model_name)
        if stats["status"] == "unknown":
            return True  # Assume healthy if no data

        max_latency = self.config.get("max_latency_seconds", 10.0)
        max_error_rate = self.config.get("max_error_rate", 0.5)

        if stats["avg_latency"] > max_latency:
            self.logger.warning(
                f"Model {model_name} is unhealthy: average latency {stats['avg_latency']:.2f}s exceeds threshold of {max_latency}s."
            )
            return False
        if stats["error_rate"] > max_error_rate:
            self.logger.warning(
                f"Model {model_name} is unhealthy: error rate {stats['error_rate']:.2%} exceeds threshold of {max_error_rate:.2%}."
            )
            return False

        return True
