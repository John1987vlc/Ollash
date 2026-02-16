"""Advanced conditional triggers system for automation rules."""

import logging
import re
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


class OperatorType(Enum):
    """Supported comparison operators."""

    EQUAL = "=="
    NOT_EQUAL = "!="
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    CONTAINS = "contains"
    NOT_CONTAINS = "!contains"
    IN_RANGE = "in_range"
    PATTERN_MATCH = "matches"


class TriggerEvaluator:
    """Evaluates complex automation rules with conditions."""

    def __init__(self):
        """Initialize the trigger evaluator."""
        self.operators: Dict[OperatorType, Callable] = {
            OperatorType.EQUAL: lambda a, b: a == b,
            OperatorType.NOT_EQUAL: lambda a, b: a != b,
            OperatorType.GREATER_THAN: lambda a, b: a > b,
            OperatorType.LESS_THAN: lambda a, b: a < b,
            OperatorType.GREATER_EQUAL: lambda a, b: a >= b,
            OperatorType.LESS_EQUAL: lambda a, b: a <= b,
            OperatorType.CONTAINS: lambda a, b: b in a if isinstance(a, (str, list)) else False,
            OperatorType.NOT_CONTAINS: lambda a, b: b not in a if isinstance(a, (str, list)) else True,
            OperatorType.IN_RANGE: self._check_range,
            OperatorType.PATTERN_MATCH: self._check_pattern,
        }

    def evaluate_condition(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Evaluate a single condition.

        Args:
            condition: Dict with 'metric', 'operator', 'value', optional 'range'
            context: Dict with available variable values

        Returns:
            True if condition is met, False otherwise
        """
        try:
            metric_path = condition.get("metric", "")
            operator = OperatorType(condition.get("operator", "=="))
            threshold = condition.get("value")

            # Extract metric value from context
            metric_value = self._extract_value(metric_path, context)

            if metric_value is None:
                logger.warning(f"Metric not found: {metric_path}")
                return False

            # Special handling for range operator
            if operator == OperatorType.IN_RANGE:
                min_val = condition.get("min")
                max_val = condition.get("max")
                return self.operators[operator](metric_value, (min_val, max_val))

            # Evaluate using operator
            return self.operators[operator](metric_value, threshold)

        except Exception as e:
            logger.error(f"Error evaluating condition {condition}: {e}")
            return False

    def evaluate_rule(self, rule: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Evaluate a complete rule with multiple conditions.

        Args:
            rule: Dict with 'conditions' list and optional 'logic' ('AND' or 'OR')
            context: Dict with available variable values

        Returns:
            True if rule is satisfied, False otherwise
        """
        try:
            conditions = rule.get("conditions", [])
            logic = rule.get("logic", "AND").upper()

            if not conditions:
                return False

            results = [self.evaluate_condition(cond, context) for cond in conditions]

            if logic == "OR":
                return any(results)
            else:  # Default to AND
                return all(results)

        except Exception as e:
            logger.error(f"Error evaluating rule {rule}: {e}")
            return False

    def _extract_value(self, path: str, context: Dict[str, Any]) -> Any:
        """
        Extract a nested value from context using dot notation.

        Examples:
            "cpu_usage" -> context["cpu_usage"]
            "memory.free" -> context["memory"]["free"]
        """
        try:
            keys = path.split(".")
            value = context
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    return None
            return value
        except Exception:
            return None

    @staticmethod
    def _check_range(value: Any, range_tuple: tuple) -> bool:
        """Check if value is within range."""
        try:
            min_val, max_val = range_tuple
            return min_val <= value <= max_val
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _check_pattern(text: str, pattern: str) -> bool:
        """Check if text matches regex pattern."""
        try:
            return bool(re.search(pattern, str(text)))
        except (TypeError, re.error):
            return False


class ConditionalTrigger:
    """Represents a conditional trigger that can be enabled/disabled."""

    def __init__(self, trigger_id: str, rule: Dict[str, Any], actions: List[Dict[str, Any]]):
        """
        Initialize a conditional trigger.

        Args:
            trigger_id: Unique identifier
            rule: Evaluation rule (conditions with logic)
            actions: List of actions to execute when rule is satisfied
        """
        self.trigger_id = trigger_id
        self.rule = rule
        self.actions = actions
        self.enabled = True
        self.last_triggered = None
        self.trigger_count = 0
        self.evaluator = TriggerEvaluator()

    def should_trigger(self, context: Dict[str, Any], cooldown_minutes: int = 0) -> bool:
        """
        Determine if this trigger should execute.

        Args:
            context: Current system/application state
            cooldown_minutes: Minimum minutes between triggers (0 = no cooldown)

        Returns:
            True if should trigger, False otherwise
        """
        if not self.enabled:
            return False

        # Check cooldown
        if self.last_triggered and cooldown_minutes > 0:
            from datetime import timedelta

            cooldown_end = self.last_triggered + timedelta(minutes=cooldown_minutes)
            if datetime.now() < cooldown_end:
                return False

        # Evaluate rule
        return self.evaluator.evaluate_rule(self.rule, context)

    def mark_triggered(self) -> None:
        """Mark this trigger as having been executed."""
        self.last_triggered = datetime.now()
        self.trigger_count += 1

    def get_actions(self) -> List[Dict[str, Any]]:
        """Get the list of actions to execute."""
        return self.actions.copy()

    def to_dict(self) -> Dict[str, Any]:
        """Convert trigger to dictionary for serialization."""
        return {
            "trigger_id": self.trigger_id,
            "rule": self.rule,
            "actions": self.actions,
            "enabled": self.enabled,
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
            "trigger_count": self.trigger_count,
        }


class TriggerManager:
    """Manages a collection of conditional triggers."""

    def __init__(self):
        """Initialize the trigger manager."""
        self.triggers: Dict[str, ConditionalTrigger] = {}
        self.history: List[Dict[str, Any]] = []

    def add_trigger(self, trigger_id: str, rule: Dict[str, Any], actions: List[Dict[str, Any]]) -> bool:
        """Add a new trigger."""
        try:
            if trigger_id in self.triggers:
                logger.warning(f"Trigger {trigger_id} already exists")
                return False

            self.triggers[trigger_id] = ConditionalTrigger(trigger_id, rule, actions)
            logger.info(f"Added trigger {trigger_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding trigger {trigger_id}: {e}")
            return False

    def remove_trigger(self, trigger_id: str) -> bool:
        """Remove a trigger."""
        if trigger_id in self.triggers:
            del self.triggers[trigger_id]
            logger.info(f"Removed trigger {trigger_id}")
            return True
        return False

    def enable_trigger(self, trigger_id: str) -> bool:
        """Enable a trigger."""
        if trigger_id in self.triggers:
            self.triggers[trigger_id].enabled = True
            return True
        return False

    def disable_trigger(self, trigger_id: str) -> bool:
        """Disable a trigger."""
        if trigger_id in self.triggers:
            self.triggers[trigger_id].enabled = False
            return True
        return False

    def evaluate_all(self, context: Dict[str, Any], cooldown_minutes: int = 0) -> List[Dict[str, Any]]:
        """
        Evaluate all active triggers against current context.

        Args:
            context: Current system state
            cooldown_minutes: Cooldown between triggers

        Returns:
            List of triggered rules with their actions
        """
        triggered = []

        for trigger_id, trigger in self.triggers.items():
            if trigger.should_trigger(context, cooldown_minutes):
                trigger.mark_triggered()
                triggered_info = {
                    "trigger_id": trigger_id,
                    "triggered_at": datetime.now().isoformat(),
                    "actions": trigger.get_actions(),
                }
                triggered.append(triggered_info)
                self.history.append(triggered_info)
                logger.info(f"Trigger {trigger_id} activated")

        return triggered

    def get_trigger_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent trigger history."""
        return self.history[-limit:]

    def to_dict(self) -> Dict[str, Any]:
        """Convert all triggers to dictionary."""
        return {trigger_id: trigger.to_dict() for trigger_id, trigger in self.triggers.items()}


# Global instance
_trigger_manager = None


def get_trigger_manager() -> TriggerManager:
    """Get or create global trigger manager instance."""
    global _trigger_manager
    if _trigger_manager is None:
        _trigger_manager = TriggerManager()
    return _trigger_manager
