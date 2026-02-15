"""Persistent metrics database for tracking system/network/security metrics over time."""

import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricsDatabase:
    """Manages persistent storage and retrieval of metrics data."""

    def __init__(self, db_path: Path):
        """
        Initialize metrics database.

        Args:
            db_path: Path to store metrics JSON files
        """
        self.db_path = Path(db_path) / "metrics"
        self.db_path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cache = {}

    def record_metric(
        self,
        category: str,
        metric_name: str,
        value: Any,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Record a new metric value.

        Args:
            category: Category of metric ('system', 'network', 'security')
            metric_name: Name of the metric (e.g., 'cpu_usage', 'disk_free')
            value: Metric value
            tags: Optional tags for additional context
        """
        with self._lock:
            try:
                timestamp = datetime.now().isoformat()
                metric_file = self.db_path / f"{category}_{metric_name}.json"

                # Load existing data
                data = []
                if metric_file.exists():
                    try:
                        with open(metric_file, "r") as f:
                            data = json.load(f)
                    except (json.JSONDecodeError, IOError):
                        data = []

                # Append new record
                record = {"timestamp": timestamp, "value": value, "tags": tags or {}}
                data.append(record)

                # Keep only last 1000 records per metric (configurable)
                if len(data) > 1000:
                    data = data[-1000:]

                # Save updated data
                with open(metric_file, "w") as f:
                    json.dump(data, f, indent=2)

                # Update cache
                cache_key = f"{category}_{metric_name}"
                self._cache[cache_key] = {
                    "last_value": value,
                    "last_timestamp": timestamp,
                    "record_count": len(data),
                }

                logger.debug(f"Recorded metric {category}/{metric_name}: {value}")

            except Exception as e:
                logger.error(f"Error recording metric {category}/{metric_name}: {e}")

    def get_metric_history(
        self,
        category: str,
        metric_name: str,
        hours: int = 24,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get historical data for a metric.

        Args:
            category: Category of metric
            metric_name: Name of the metric
            hours: How many hours back to retrieve (default: 24)
            limit: Maximum number of records to return

        Returns:
            List of metric records with timestamp and value
        """
        try:
            metric_file = self.db_path / f"{category}_{metric_name}.json"

            if not metric_file.exists():
                return []

            with self._lock:
                with open(metric_file, "r") as f:
                    data = json.load(f)

            # Filter by time
            cutoff_time = datetime.now() - timedelta(hours=hours)
            filtered = [
                record
                for record in data
                if datetime.fromisoformat(record["timestamp"]) > cutoff_time
            ]

            # Apply limit
            if limit:
                filtered = filtered[-limit:]

            return filtered

        except Exception as e:
            logger.error(
                f"Error retrieving metric history {category}/{metric_name}: {e}"
            )
            return []

    def get_latest_metric(
        self, category: str, metric_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the most recent value of a metric.

        Args:
            category: Category of metric
            metric_name: Name of the metric

        Returns:
            Latest record or None if not found
        """
        try:
            metric_file = self.db_path / f"{category}_{metric_name}.json"

            if not metric_file.exists():
                return None

            with self._lock:
                with open(metric_file, "r") as f:
                    data = json.load(f)

            if data:
                return data[-1]
            return None

        except Exception as e:
            logger.error(
                f"Error retrieving latest metric {category}/{metric_name}: {e}"
            )
            return None

    def get_metric_stats(
        self, category: str, metric_name: str, hours: int = 24
    ) -> Optional[Dict[str, Any]]:
        """
        Get statistics (min, max, avg) for a metric over a time period.

        Args:
            category: Category of metric
            metric_name: Name of the metric
            hours: Time period in hours

        Returns:
            Dictionary with min, max, avg, latest, count
        """
        try:
            history = self.get_metric_history(category, metric_name, hours=hours)

            if not history:
                return None

            # Extract numeric values
            values = []
            for record in history:
                try:
                    if isinstance(record["value"], (int, float)):
                        values.append(record["value"])
                except (KeyError, TypeError):
                    pass

            if not values:
                return None

            return {
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "latest": values[-1],
                "count": len(values),
                "period_hours": hours,
            }

        except Exception as e:
            logger.error(f"Error calculating stats for {category}/{metric_name}: {e}")
            return None

    def clear_old_metrics(self, days: int = 30) -> None:
        """
        Remove metric records older than specified days.

        Args:
            days: Age threshold in days
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=days)
            cutoff_iso = cutoff_time.isoformat()

            with self._lock:
                for metric_file in self.db_path.glob("*.json"):
                    try:
                        with open(metric_file, "r") as f:
                            data = json.load(f)

                        # Filter out old records
                        filtered = [
                            record
                            for record in data
                            if record.get("timestamp", "") > cutoff_iso
                        ]

                        # Save cleaned data
                        with open(metric_file, "w") as f:
                            json.dump(filtered, f, indent=2)

                        logger.debug(
                            f"Cleaned {metric_file.name}: {len(data) - len(filtered)} old records removed"
                        )

                    except Exception as e:
                        logger.error(f"Error cleaning {metric_file.name}: {e}")

        except Exception as e:
            logger.error(f"Error clearing old metrics: {e}")


# Global instance
_metrics_db = None


def get_metrics_database(db_path: Optional[Path] = None) -> MetricsDatabase:
    """Get or create global metrics database instance."""
    global _metrics_db
    if _metrics_db is None:
        if db_path is None:
            db_path = Path.cwd()
        _metrics_db = MetricsDatabase(db_path)
    return _metrics_db
