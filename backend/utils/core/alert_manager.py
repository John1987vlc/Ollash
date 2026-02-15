"""
Alert Manager - Handles proactive system alerts and thresholds
Monitors metrics and triggers notifications when thresholds are exceeded
"""

import logging
from datetime import datetime
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages system alerts and threshold monitoring."""

    # Alert severity levels
    SEVERITY_INFO = "info"
    SEVERITY_WARNING = "warning"
    SEVERITY_CRITICAL = "critical"
    SEVERITY_LEVELS = [SEVERITY_INFO, SEVERITY_WARNING, SEVERITY_CRITICAL]

    def __init__(self, notification_manager=None, event_publisher=None):
        """
        Initialize alert manager.

        Args:
            notification_manager: NotificationManager instance for sending alerts
            event_publisher: EventPublisher instance for publishing events
        """
        self.notification_manager = notification_manager
        self.event_publisher = event_publisher
        self.alerts = {}  # Maps alert_id to alert config
        self.alert_history = []  # Store recent alerts for dashboard
        self.max_history = 100
        self._lock = Lock()
        self.alert_callbacks = {}  # Maps alert_id to custom handlers

    def register_alert(self, alert_id: str, alert_config: Dict[str, Any]) -> bool:
        """
        Register a new alert with thresholds.

        Args:
            alert_id: Unique alert identifier
            alert_config: Alert configuration dict with:
                - name: Human-readable name
                - description: Alert description
                - severity: info, warning, or critical
                - entity: What is being monitored (cpu, memory, disk, etc.)
                - threshold: Threshold value
                - operator: Comparison operator (>, <, >=, <=, ==)
                - cooldown_seconds: Minimum time between alerts of same type

        Returns:
            True if alert was registered successfully
        """
        try:
            with self._lock:
                self.alerts[alert_id] = {
                    **alert_config,
                    "last_triggered": None,
                    "trigger_count": 0,
                    "enabled": True,
                }
            logger.info(f"✅ Registered alert: {alert_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to register alert {alert_id}: {e}")
            return False

    def register_alert_callback(self, alert_id: str, callback: Callable):
        """
        Register a custom callback for an alert.
        Callback receives (alert_id, metric_value, alert_config).

        Args:
            alert_id: Alert identifier
            callback: Function to call when alert triggers
        """
        with self._lock:
            self.alert_callbacks[alert_id] = callback
            logger.info(f"Registered callback for alert: {alert_id}")

    def check_alert(
        self, alert_id: str, current_value: float
    ) -> Optional[Dict[str, Any]]:
        """
        Check if an alert should trigger based on current metric value.

        Args:
            alert_id: Alert identifier
            current_value: Current metric value to check

        Returns:
            Alert info if triggered, None otherwise
        """
        with self._lock:
            if alert_id not in self.alerts:
                logger.warning(f"Alert not found: {alert_id}")
                return None

            alert = self.alerts[alert_id]

            if not alert.get("enabled", True):
                return None

            # Check if alert should trigger
            threshold = alert.get("threshold")
            operator = alert.get("operator", ">")
            severity = alert.get("severity", self.SEVERITY_WARNING)

            should_trigger = self._evaluate_threshold(
                current_value, threshold, operator
            )

            if not should_trigger:
                return None

            # Check cooldown period
            cooldown = alert.get("cooldown_seconds", 300)
            last_triggered = alert.get("last_triggered")

            if last_triggered:
                time_since = (datetime.now() - last_triggered).total_seconds()
                if time_since < cooldown:
                    return None  # Too soon, cooldown not elapsed

            # Alert should trigger
            alert["last_triggered"] = datetime.now()
            alert["trigger_count"] = alert.get("trigger_count", 0) + 1

            alert_info = {
                "alert_id": alert_id,
                "name": alert.get("name", alert_id),
                "description": alert.get("description", ""),
                "severity": severity,
                "entity": alert.get("entity", "unknown"),
                "current_value": current_value,
                "threshold": threshold,
                "operator": operator,
                "timestamp": datetime.now().isoformat(),
                "trigger_count": alert["trigger_count"],
            }

            # Add to history
            self.alert_history.append(alert_info)
            if len(self.alert_history) > self.max_history:
                self.alert_history.pop(0)

            return alert_info

    def trigger_alert(
        self, alert_id: str, alert_info: Dict[str, Any], channels: List[str] = None
    ) -> bool:
        """
        Trigger an alert with notifications.

        Args:
            alert_id: Alert identifier
            alert_info: Alert information dict
            channels: Notification channels (ui, email, log)

        Returns:
            True if alert was triggered successfully
        """
        try:
            if channels is None:
                channels = ["ui", "log"]

            severity = alert_info.get("severity", self.SEVERITY_WARNING)
            title = alert_info.get("name", alert_id)
            message = alert_info.get("description", "")

            # Add metric context to message
            current = alert_info.get("current_value")
            threshold = alert_info.get("threshold")
            operator = alert_info.get("operator", ">")

            if current is not None and threshold is not None:
                message += (
                    f"\n\nCurrent Value: {current}\nThreshold: {threshold} ({operator})"
                )

            # Log the alert
            if "log" in channels:
                log_level = {
                    self.SEVERITY_INFO: logging.INFO,
                    self.SEVERITY_WARNING: logging.WARNING,
                    self.SEVERITY_CRITICAL: logging.CRITICAL,
                }.get(severity, logging.INFO)

                logger.log(
                    log_level, f"🚨 ALERT [{severity.upper()}]: {title} - {message}"
                )

            # UI notification
            if "ui" in channels and self.notification_manager:
                self.notification_manager.send_ui_notification(
                    message=message,
                    notification_type=severity,
                    title=f"🚨 {title}",
                    data={"alert_id": alert_id, **alert_info},
                )

            # Email notification
            if "email" in channels and self.notification_manager:
                self.notification_manager.send_email(
                    subject=f"[{severity.upper()}] Ollash Alert: {title}",
                    to_email=None,  # Use subscribed emails
                    content=self._format_alert_email(alert_info),
                )

            # Execute custom callback if registered
            if alert_id in self.alert_callbacks:
                try:
                    self.alert_callbacks[alert_id](alert_id, alert_info)
                except Exception as e:
                    logger.error(f"Error executing callback for {alert_id}: {e}")

            # Publish event
            if self.event_publisher:
                self.event_publisher.publish("alert_triggered", alert_info)

            return True

        except Exception as e:
            logger.error(f"❌ Failed to trigger alert {alert_id}: {e}")
            return False

    def _evaluate_threshold(
        self, current_value: float, threshold: float, operator: str
    ) -> bool:
        """Evaluate if threshold is exceeded."""
        try:
            if operator == ">":
                return current_value > threshold
            elif operator == "<":
                return current_value < threshold
            elif operator == ">=":
                return current_value >= threshold
            elif operator == "<=":
                return current_value <= threshold
            elif operator == "==":
                return current_value == threshold
            elif operator == "!=":
                return current_value != threshold
            else:
                logger.warning(f"Unknown operator: {operator}")
                return False
        except Exception as e:
            logger.error(f"Error evaluating threshold: {e}")
            return False

    def _format_alert_email(self, alert_info: Dict[str, Any]) -> str:
        """Format alert info for email."""
        return f"""
Ollash System Alert

Alert: {alert_info.get('name', 'Unknown')}
Severity: {alert_info.get('severity', 'Unknown').upper()}
Entity: {alert_info.get('entity', 'Unknown')}
Description: {alert_info.get('description', '')}

Current Value: {alert_info.get('current_value')}
Threshold: {alert_info.get('threshold')} ({alert_info.get('operator', '?')})
Timestamp: {alert_info.get('timestamp')}

Please review your system and take any necessary action.
        """

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all currently enabled alerts."""
        with self._lock:
            return [a for a in self.alerts.values() if a.get("enabled", True)]

    def get_alert_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get alert history."""
        return self.alert_history[-limit:]

    def disable_alert(self, alert_id: str) -> bool:
        """Disable an alert."""
        with self._lock:
            if alert_id in self.alerts:
                self.alerts[alert_id]["enabled"] = False
                logger.info(f"Disabled alert: {alert_id}")
                return True
        return False

    def enable_alert(self, alert_id: str) -> bool:
        """Enable an alert."""
        with self._lock:
            if alert_id in self.alerts:
                self.alerts[alert_id]["enabled"] = True
                logger.info(f"Enabled alert: {alert_id}")
                return True
        return False

    def clear_history(self):
        """Clear alert history."""
        self.alert_history.clear()
        logger.info("Cleared alert history")


# Singleton instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager(notification_manager=None, event_publisher=None) -> AlertManager:
    """Get or create the alert manager singleton."""
    global _alert_manager

    if _alert_manager is None:
        _alert_manager = AlertManager(notification_manager, event_publisher)

    return _alert_manager
