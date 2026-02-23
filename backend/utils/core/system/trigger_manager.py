"""Unified trigger management system.

Provides two complementary trigger managers:

- ``TriggerManager``: Lightweight rule-based triggers with multi-condition AND/OR
  evaluation, cooldown support, and action lists.  Used by automation_executor and
  the triggers REST API.

- ``AdvancedTriggerManager``: Complex triggers with composite AND/OR/NOT/XOR logic,
  state machines, trigger dependencies, time windows, and conflict detection.
  Used by the Phase-6 blueprint.

Both classes share ``OperatorType`` and ``TriggerEvaluator`` to avoid code
duplication in condition evaluation.
"""

import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared enumerations
# ---------------------------------------------------------------------------

class OperatorType(Enum):
    """Supported comparison operators (shared by both managers)."""

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
    IN = "in"


class LogicOperator(Enum):
    """Logical operators for combining composite conditions (AdvancedTriggerManager)."""

    AND = "and"
    OR = "or"
    NOT = "not"
    XOR = "xor"


class TriggerState(Enum):
    """State of a trigger (AdvancedTriggerManager)."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    FIRED = "fired"
    COOLDOWN = "cooldown"
    ERROR = "error"


class TimeWindowType(Enum):
    """Types of time windows (AdvancedTriggerManager)."""

    LAST_MINUTES = "last_minutes"
    LAST_HOURS = "last_hours"
    LAST_DAYS = "last_days"
    SPECIFIC_TIME = "specific_time"
    BUSINESS_HOURS = "business_hours"


# ---------------------------------------------------------------------------
# Advanced dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CompositeTriggerCondition:
    """A condition that combines multiple sub-conditions with logic."""

    id: str
    operator: LogicOperator
    sub_conditions: List[Dict[str, Any]]
    weight: float = 1.0
    time_window: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TriggerDependency:
    """Dependency between triggers."""

    dependent_trigger_id: str
    required_trigger_id: str
    condition: str  # "must_have_fired", "must_not_fire", etc.
    within_timeframe: Optional[int] = None  # Milliseconds


# ---------------------------------------------------------------------------
# Shared condition evaluator
# ---------------------------------------------------------------------------

class TriggerEvaluator:
    """Evaluates automation rules with typed operator support."""

    def __init__(self) -> None:
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
            OperatorType.IN: lambda a, b: a in b if isinstance(b, (list, tuple, set)) else False,
        }

    def evaluate_condition(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Evaluate a single condition against context."""
        try:
            metric_path = condition.get("metric", "")
            operator = OperatorType(condition.get("operator", "=="))
            threshold = condition.get("value")
            metric_value = self._extract_value(metric_path, context)

            if metric_value is None:
                logger.warning(f"Metric not found: {metric_path}")
                return False

            if operator == OperatorType.IN_RANGE:
                return self.operators[operator](metric_value, (condition.get("min"), condition.get("max")))

            return self.operators[operator](metric_value, threshold)

        except Exception as e:
            logger.error(f"Error evaluating condition {condition}: {e}")
            return False

    def evaluate_rule(self, rule: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Evaluate a complete rule with AND/OR logic."""
        try:
            conditions = rule.get("conditions", [])
            logic = rule.get("logic", "AND").upper()
            if not conditions:
                return False
            results = [self.evaluate_condition(c, context) for c in conditions]
            return any(results) if logic == "OR" else all(results)
        except Exception as e:
            logger.error(f"Error evaluating rule {rule}: {e}")
            return False

    def _extract_value(self, path: str, context: Dict[str, Any]) -> Any:
        """Extract a nested value from context using dot notation."""
        try:
            value = context
            for key in path.split("."):
                value = value.get(key) if isinstance(value, dict) else None
            return value
        except Exception:
            return None

    @staticmethod
    def _check_range(value: Any, range_tuple: tuple) -> bool:
        try:
            min_val, max_val = range_tuple
            return min_val <= value <= max_val
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _check_pattern(text: str, pattern: str) -> bool:
        try:
            return bool(re.search(pattern, str(text)))
        except (TypeError, re.error):
            return False


# ---------------------------------------------------------------------------
# Basic trigger
# ---------------------------------------------------------------------------

class ConditionalTrigger:
    """A single conditional trigger with cooldown support."""

    def __init__(self, trigger_id: str, rule: Dict[str, Any], actions: List[Dict[str, Any]]) -> None:
        self.trigger_id = trigger_id
        self.rule = rule
        self.actions = actions
        self.enabled = True
        self.last_triggered: Optional[datetime] = None
        self.trigger_count = 0
        self.evaluator = TriggerEvaluator()

    def should_trigger(self, context: Dict[str, Any], cooldown_minutes: int = 0) -> bool:
        if not self.enabled:
            return False
        if self.last_triggered and cooldown_minutes > 0:
            if datetime.now() < self.last_triggered + timedelta(minutes=cooldown_minutes):
                return False
        return self.evaluator.evaluate_rule(self.rule, context)

    def mark_triggered(self) -> None:
        self.last_triggered = datetime.now()
        self.trigger_count += 1

    def get_actions(self) -> List[Dict[str, Any]]:
        return self.actions.copy()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "rule": self.rule,
            "actions": self.actions,
            "enabled": self.enabled,
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
            "trigger_count": self.trigger_count,
        }


# ---------------------------------------------------------------------------
# TriggerManager (lightweight, rule-based)
# ---------------------------------------------------------------------------

class TriggerManager:
    """Manages a collection of lightweight conditional triggers."""

    def __init__(self) -> None:
        self.triggers: Dict[str, ConditionalTrigger] = {}
        self.history: List[Dict[str, Any]] = []

    def add_trigger(self, trigger_id: str, rule: Dict[str, Any], actions: List[Dict[str, Any]]) -> bool:
        if trigger_id in self.triggers:
            logger.warning(f"Trigger {trigger_id} already exists")
            return False
        try:
            self.triggers[trigger_id] = ConditionalTrigger(trigger_id, rule, actions)
            logger.info(f"Added trigger {trigger_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding trigger {trigger_id}: {e}")
            return False

    def remove_trigger(self, trigger_id: str) -> bool:
        if trigger_id in self.triggers:
            del self.triggers[trigger_id]
            logger.info(f"Removed trigger {trigger_id}")
            return True
        return False

    def enable_trigger(self, trigger_id: str) -> bool:
        if trigger_id in self.triggers:
            self.triggers[trigger_id].enabled = True
            return True
        return False

    def disable_trigger(self, trigger_id: str) -> bool:
        if trigger_id in self.triggers:
            self.triggers[trigger_id].enabled = False
            return True
        return False

    def evaluate_all(self, context: Dict[str, Any], cooldown_minutes: int = 0) -> List[Dict[str, Any]]:
        triggered = []
        for trigger_id, trigger in self.triggers.items():
            if trigger.should_trigger(context, cooldown_minutes):
                trigger.mark_triggered()
                entry = {
                    "trigger_id": trigger_id,
                    "triggered_at": datetime.now().isoformat(),
                    "actions": trigger.get_actions(),
                }
                triggered.append(entry)
                self.history.append(entry)
                logger.info(f"Trigger {trigger_id} activated")
        return triggered

    def get_trigger_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.history[-limit:]

    def to_dict(self) -> Dict[str, Any]:
        return {tid: t.to_dict() for tid, t in self.triggers.items()}


# ---------------------------------------------------------------------------
# AdvancedTriggerManager (composite, state machine, dependencies)
# ---------------------------------------------------------------------------

class AdvancedTriggerManager:
    """
    Manages complex automation triggers with advanced logic.

    Features:
    - Composite conditions (AND/OR/NOT/XOR)
    - Time-window conditions
    - State tracking for triggers
    - Dependency resolution
    - Conflict detection
    - Cooling periods and throttling
    """

    def __init__(self) -> None:
        self.triggers: Dict[str, Dict[str, Any]] = {}
        self.trigger_states: Dict[str, TriggerState] = {}
        self.dependencies: Dict[str, List[TriggerDependency]] = {}
        self.firing_history: List[Dict[str, Any]] = []
        self.max_history = 1000
        self.max_fires_per_minute = 10
        self._evaluator = TriggerEvaluator()
        logger.info("AdvancedTriggerManager initialized")

    def register_composite_trigger(
        self,
        trigger_id: str,
        name: str,
        composite_condition: CompositeTriggerCondition,
        action_callback: Optional[Callable] = None,
        cooldown_seconds: int = 0,
        enabled: bool = True,
    ) -> bool:
        try:
            self.triggers[trigger_id] = {
                "id": trigger_id,
                "name": name,
                "condition": composite_condition.to_dict(),
                "action_callback": action_callback,
                "cooldown_seconds": cooldown_seconds,
                "enabled": enabled,
                "created_at": datetime.now().isoformat(),
                "last_fired": None,
                "fire_count": 0,
            }
            self.trigger_states[trigger_id] = TriggerState.INACTIVE
            logger.info(f"Composite trigger registered: {name} ({trigger_id})")
            return True
        except Exception as e:
            logger.error(f"Failed to register trigger: {e}")
            return False

    def register_state_machine_trigger(
        self,
        trigger_id: str,
        name: str,
        states: List[str],
        initial_state: str,
        transitions: Dict[str, List[Dict[str, Any]]],
        action_on_transition: Optional[Callable] = None,
    ) -> bool:
        try:
            self.triggers[trigger_id] = {
                "id": trigger_id,
                "name": name,
                "type": "state_machine",
                "states": states,
                "current_state": initial_state,
                "transitions": transitions,
                "action_on_transition": action_on_transition,
                "state_enter_time": datetime.now().isoformat(),
                "state_history": [(initial_state, datetime.now().isoformat())],
            }
            self.trigger_states[trigger_id] = TriggerState.ACTIVE
            logger.info(f"State machine trigger registered: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to register state machine trigger: {e}")
            return False

    def add_trigger_dependency(
        self,
        dependent_trigger_id: str,
        required_trigger_id: str,
        condition: str = "must_have_fired",
        within_timeframe_ms: Optional[int] = None,
    ) -> bool:
        try:
            dep = TriggerDependency(
                dependent_trigger_id=dependent_trigger_id,
                required_trigger_id=required_trigger_id,
                condition=condition,
                within_timeframe=within_timeframe_ms,
            )
            self.dependencies.setdefault(dependent_trigger_id, []).append(dep)
            logger.info(f"Dependency added: {dependent_trigger_id} depends on {required_trigger_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add dependency: {e}")
            return False

    def evaluate_trigger(self, trigger_id: str, context: Dict[str, Any]) -> bool:
        try:
            if trigger_id not in self.triggers:
                logger.warning(f"Trigger not found: {trigger_id}")
                return False
            trigger = self.triggers[trigger_id]
            if not trigger.get("enabled", True):
                return False
            if not self._is_cooldown_expired(trigger_id):
                logger.debug(f"Trigger {trigger_id} is in cooldown")
                return False
            if not self._check_dependencies(trigger_id, context):
                logger.debug(f"Trigger {trigger_id} dependencies not met")
                return False
            if trigger.get("type") == "state_machine":
                return self._evaluate_state_machine(trigger_id, context)
            return self._evaluate_composite_condition(trigger.get("condition"), context)
        except Exception as e:
            logger.error(f"Error evaluating trigger {trigger_id}: {e}")
            self.trigger_states[trigger_id] = TriggerState.ERROR
            return False

    def fire_trigger(self, trigger_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            if trigger_id not in self.triggers:
                return {"success": False, "error": "Trigger not found"}
            trigger = self.triggers[trigger_id]
            result: Dict[str, Any] = {
                "success": True,
                "trigger_id": trigger_id,
                "trigger_name": trigger.get("name"),
                "fired_at": datetime.now().isoformat(),
                "callback_result": None,
            }
            if trigger.get("action_callback"):
                try:
                    result["callback_result"] = trigger["action_callback"](context or {})
                except Exception as e:
                    logger.error(f"Callback error for {trigger_id}: {e}")
                    result["callback_error"] = str(e)
            trigger["last_fired"] = datetime.now().isoformat()
            trigger["fire_count"] = trigger.get("fire_count", 0) + 1
            self.trigger_states[trigger_id] = (
                TriggerState.COOLDOWN if trigger.get("cooldown_seconds", 0) > 0 else TriggerState.FIRED
            )
            self.firing_history.append(result)
            if len(self.firing_history) > self.max_history:
                self.firing_history = self.firing_history[-self.max_history:]
            return result
        except Exception as e:
            logger.error(f"Error firing trigger {trigger_id}: {e}")
            return {"success": False, "error": str(e)}

    def detect_conflicts(self) -> List[Dict[str, Any]]:
        conflicts = []
        trigger_ids = list(self.triggers.keys())
        for i, tid1 in enumerate(trigger_ids):
            for tid2 in trigger_ids[i + 1:]:
                if self._triggers_could_conflict(tid1, tid2):
                    conflicts.append({
                        "trigger1": tid1,
                        "trigger2": tid2,
                        "trigger1_name": self.triggers[tid1].get("name"),
                        "trigger2_name": self.triggers[tid2].get("name"),
                        "conflict_type": "simultaneous_fire",
                        "recommendation": "Add dependency or exclusive conditions",
                    })
        return conflicts

    def get_trigger_status(self, trigger_id: Optional[str] = None) -> Dict[str, Any]:
        if trigger_id:
            if trigger_id not in self.triggers:
                return {"error": "Trigger not found"}
            t = self.triggers[trigger_id]
            return {
                "id": trigger_id,
                "name": t.get("name"),
                "state": self.trigger_states.get(trigger_id, TriggerState.INACTIVE).value,
                "enabled": t.get("enabled"),
                "fire_count": t.get("fire_count"),
                "last_fired": t.get("last_fired"),
                "in_cooldown": self.trigger_states.get(trigger_id) == TriggerState.COOLDOWN,
            }
        return {
            tid: {
                "name": t.get("name"),
                "state": self.trigger_states.get(tid, TriggerState.INACTIVE).value,
                "fire_count": t.get("fire_count", 0),
            }
            for tid, t in self.triggers.items()
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _evaluate_composite_condition(
        self, condition: Optional[Dict[str, Any]], context: Dict[str, Any]
    ) -> bool:
        if not condition:
            return False
        operator = LogicOperator(condition.get("operator", "and"))
        sub_conditions = condition.get("sub_conditions", [])
        time_window = condition.get("time_window")
        if time_window and not self._is_within_time_window(time_window):
            return False
        results = [
            self._evaluate_composite_condition(sc, context) if "sub_conditions" in sc
            else self._evaluator.evaluate_condition(sc, context)
            for sc in sub_conditions
        ]
        if operator == LogicOperator.AND:
            return all(results) if results else False
        if operator == LogicOperator.OR:
            return any(results) if results else False
        if operator == LogicOperator.NOT:
            return not results[0] if results else True
        if operator == LogicOperator.XOR:
            return sum(results) == 1
        return False

    def _evaluate_state_machine(self, trigger_id: str, context: Dict[str, Any]) -> bool:
        trigger = self.triggers[trigger_id]
        current_state = trigger.get("current_state")
        for transition in trigger.get("transitions", {}).get(current_state, []):
            if self._evaluate_composite_condition(transition.get("condition"), context):
                return self._transition_state(trigger_id, transition.get("to_state"))
        return False

    def _transition_state(self, trigger_id: str, new_state: str) -> bool:
        trigger = self.triggers[trigger_id]
        old_state = trigger.get("current_state")
        if new_state == old_state:
            return False
        trigger["current_state"] = new_state
        trigger["state_enter_time"] = datetime.now().isoformat()
        trigger.setdefault("state_history", []).append((new_state, datetime.now().isoformat()))
        if trigger.get("action_on_transition"):
            try:
                trigger["action_on_transition"](old_state, new_state)
            except Exception as e:
                logger.error(f"State transition action error: {e}")
        logger.info(f"Trigger {trigger_id} transitioned: {old_state} -> {new_state}")
        return True

    def _is_cooldown_expired(self, trigger_id: str) -> bool:
        trigger = self.triggers.get(trigger_id)
        if not trigger:
            return True
        cooldown_seconds = trigger.get("cooldown_seconds", 0)
        if cooldown_seconds == 0:
            return True
        last_fired = trigger.get("last_fired")
        if not last_fired:
            return True
        return (datetime.now() - datetime.fromisoformat(last_fired)).total_seconds() >= cooldown_seconds

    def _check_dependencies(self, trigger_id: str, context: Dict[str, Any]) -> bool:
        for dep in self.dependencies.get(trigger_id, []):
            required = self.triggers.get(dep.required_trigger_id)
            if not required:
                return False
            if dep.condition == "must_have_fired" and not required.get("last_fired"):
                return False
            if dep.condition == "must_not_fire" and required.get("last_fired"):
                return False
        return True

    def _is_within_time_window(self, time_window: Dict[str, Any]) -> bool:
        window_type = TimeWindowType(time_window.get("type"))
        if window_type == TimeWindowType.BUSINESS_HOURS:
            now = datetime.now()
            return 9 <= now.hour < 17 and now.weekday() < 5
        return True

    def _triggers_could_conflict(self, tid1: str, tid2: str) -> bool:
        t1 = self.triggers[tid1]
        t2 = self.triggers[tid2]
        return t1.get("enabled", True) and t2.get("enabled", True) and tid1 != tid2


# ---------------------------------------------------------------------------
# Global singletons
# ---------------------------------------------------------------------------

_trigger_manager: Optional[TriggerManager] = None
_advanced_trigger_manager: Optional[AdvancedTriggerManager] = None


def get_trigger_manager() -> TriggerManager:
    """Get or create the global TriggerManager instance."""
    global _trigger_manager
    if _trigger_manager is None:
        _trigger_manager = TriggerManager()
    return _trigger_manager


def get_advanced_trigger_manager() -> AdvancedTriggerManager:
    """Get or create the global AdvancedTriggerManager instance."""
    global _advanced_trigger_manager
    if _advanced_trigger_manager is None:
        _advanced_trigger_manager = AdvancedTriggerManager()
    return _advanced_trigger_manager
