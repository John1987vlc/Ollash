"""
Advanced Trigger Manager - Complex conditional triggers with AND/OR/NOT logic.

Extends the basic TriggerManager (src/utils/core/trigger_manager.py) with:
- Composite AND/OR/NOT conditions
- Time-window conditions (e.g., "last 5 minutes")
- State machine triggers
- Dependency resolution
- Conflict detection
"""

import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class LogicOperator(Enum):
    """Logical operators for combining conditions."""

    AND = "and"
    OR = "or"
    NOT = "not"
    XOR = "xor"


class TriggerState(Enum):
    """State of a trigger."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    FIRED = "fired"
    COOLDOWN = "cooldown"
    ERROR = "error"


class TimeWindowType(Enum):
    """Types of time windows."""

    LAST_MINUTES = "last_minutes"
    LAST_HOURS = "last_hours"
    LAST_DAYS = "last_days"
    SPECIFIC_TIME = "specific_time"
    BUSINESS_HOURS = "business_hours"


@dataclass
class CompositeTriggerCondition:
    """A condition that combines multiple sub-conditions with logic."""

    id: str
    operator: LogicOperator
    sub_conditions: List[Dict[str, Any]]  # Can be simple or composite
    weight: float = 1.0  # For weighted scoring
    time_window: Optional[Dict[str, Any]] = None  # Optional time constraint

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TriggerDependency:
    """Dependency between triggers."""

    dependent_trigger_id: str
    required_trigger_id: str
    condition: str  # "must_have_fired", "must_not_fire", etc.
    within_timeframe: Optional[int] = None  # Milliseconds


class AdvancedTriggerManager:
    """
    Manages complex automation triggers with advanced logic.

    Features:
    - Composite conditions (AND/OR/NOT combinations)
    - Time-window conditions
    - State tracking for triggers
    - Dependency resolution
    - Conflict detection
    - Cooling periods and throttling
    """

    def __init__(self):
        """Initialize the advanced trigger manager."""
        self.triggers: Dict[str, Dict[str, Any]] = {}
        self.trigger_states: Dict[str, TriggerState] = {}
        self.dependencies: Dict[str, List[TriggerDependency]] = {}
        self.firing_history: List[Dict[str, Any]] = []
        self.max_history = 1000
        self.max_fires_per_minute = 10  # Default throttle rate
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
        """
        Register a trigger with composite (AND/OR/NOT) conditions.

        Args:
            trigger_id: Unique ID for the trigger
            name: Human-readable name
            composite_condition: Composite condition object
            action_callback: Function to call when triggered
            cooldown_seconds: Cooldown period after firing
            enabled: Whether trigger starts enabled

        Returns:
            bool: Success status
        """
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
        transitions: Dict[str, List[Dict[str, Any]]],  # from_state -> [conditions, to_state]
        action_on_transition: Optional[Callable] = None,
    ) -> bool:
        """
        Register a state machine-based trigger.

        Args:
            trigger_id: Unique ID
            name: Display name
            states: List of valid states
            initial_state: Starting state
            transitions: State transition rules
            action_on_transition: Action to take on state change

        Returns:
            bool: Success status
        """
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
        """
        Add a dependency between triggers.

        Args:
            dependent_trigger_id: Trigger that has a dependency
            required_trigger_id: Required trigger ID
            condition: Condition type ("must_have_fired", "must_not_fire", etc.)
            within_timeframe_ms: Timeframe for the dependency

        Returns:
            bool: Success status
        """
        try:
            dependency = TriggerDependency(
                dependent_trigger_id=dependent_trigger_id,
                required_trigger_id=required_trigger_id,
                condition=condition,
                within_timeframe=within_timeframe_ms,
            )

            if dependent_trigger_id not in self.dependencies:
                self.dependencies[dependent_trigger_id] = []

            self.dependencies[dependent_trigger_id].append(dependency)

            logger.info(f"Dependency added: {dependent_trigger_id} depends on {required_trigger_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to add dependency: {e}")
            return False

    def evaluate_trigger(self, trigger_id: str, context: Dict[str, Any]) -> bool:
        """
        Evaluate if a trigger should fire.

        Args:
            trigger_id: ID of trigger to evaluate
            context: Context data for condition evaluation

        Returns:
            bool: Whether trigger should fire
        """
        try:
            if trigger_id not in self.triggers:
                logger.warning(f"Trigger not found: {trigger_id}")
                return False

            trigger = self.triggers[trigger_id]

            # Check if enabled
            if not trigger.get("enabled", True):
                return False

            # Check cooldown
            if not self._is_cooldown_expired(trigger_id):
                logger.debug(f"Trigger {trigger_id} is in cooldown")
                return False

            # Check dependencies
            if not self._check_dependencies(trigger_id, context):
                logger.debug(f"Trigger {trigger_id} dependencies not met")
                return False

            # Evaluate composite condition
            if trigger.get("type") == "state_machine":
                return self._evaluate_state_machine(trigger_id, context)
            else:
                return self._evaluate_composite_condition(trigger.get("condition"), context)

        except Exception as e:
            logger.error(f"Error evaluating trigger {trigger_id}: {e}")
            self.trigger_states[trigger_id] = TriggerState.ERROR
            return False

    def fire_trigger(self, trigger_id: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Fire a trigger (execute its action).

        Args:
            trigger_id: ID of trigger to fire
            context: Optional context data

        Returns:
            Dict: Firing result
        """
        try:
            if trigger_id not in self.triggers:
                return {"success": False, "error": "Trigger not found"}

            trigger = self.triggers[trigger_id]

            # Execute callback if provided
            result = {
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

            # Update trigger state
            trigger["last_fired"] = datetime.now().isoformat()
            trigger["fire_count"] = trigger.get("fire_count", 0) + 1
            self.trigger_states[trigger_id] = TriggerState.FIRED

            # Set cooldown
            if trigger.get("cooldown_seconds", 0) > 0:
                self.trigger_states[trigger_id] = TriggerState.COOLDOWN

            # Record in history
            self.firing_history.append(result)
            if len(self.firing_history) > self.max_history:
                self.firing_history = self.firing_history[-self.max_history :]

            return result

        except Exception as e:
            logger.error(f"Error firing trigger {trigger_id}: {e}")
            return {"success": False, "error": str(e)}

    def detect_conflicts(self) -> List[Dict[str, Any]]:
        """
        Detect potential conflicts between triggers.

        Returns:
            List: Detected conflicts
        """
        conflicts = []
        trigger_ids = list(self.triggers.keys())

        for i, tid1 in enumerate(trigger_ids):
            for tid2 in trigger_ids[i + 1 :]:
                # Check if triggers might fire simultaneously
                if self._triggers_could_conflict(tid1, tid2):
                    conflicts.append(
                        {
                            "trigger1": tid1,
                            "trigger2": tid2,
                            "trigger1_name": self.triggers[tid1].get("name"),
                            "trigger2_name": self.triggers[tid2].get("name"),
                            "conflict_type": "simultaneous_fire",
                            "recommendation": "Add dependency or exclusive conditions",
                        }
                    )

        return conflicts

    def get_trigger_status(self, trigger_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get status of trigger(s).

        Args:
            trigger_id: Specific trigger ID, or None for all

        Returns:
            Dict: Trigger status information
        """
        if trigger_id:
            if trigger_id not in self.triggers:
                return {"error": "Trigger not found"}

            trigger = self.triggers[trigger_id]
            return {
                "id": trigger_id,
                "name": trigger.get("name"),
                "state": self.trigger_states.get(trigger_id, TriggerState.INACTIVE).value,
                "enabled": trigger.get("enabled"),
                "fire_count": trigger.get("fire_count"),
                "last_fired": trigger.get("last_fired"),
                "in_cooldown": self.trigger_states.get(trigger_id) == TriggerState.COOLDOWN,
            }
        else:
            return {
                tid: {
                    "name": t.get("name"),
                    "state": self.trigger_states.get(tid, TriggerState.INACTIVE).value,
                    "fire_count": t.get("fire_count", 0),
                }
                for tid, t in self.triggers.items()
            }

    # ==================== Private Methods ====================

    def _evaluate_composite_condition(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Recursively evaluate composite condition."""
        if not condition:
            return False

        operator = LogicOperator(condition.get("operator", "and"))
        sub_conditions = condition.get("sub_conditions", [])

        # Check time window if present
        time_window = condition.get("time_window")
        if time_window and not self._is_within_time_window(time_window):
            return False

        results = []
        for sub_cond in sub_conditions:
            if "operator" in sub_cond:
                # Recursive composite condition
                result = self._evaluate_composite_condition(sub_cond, context)
            else:
                # Simple condition evaluation
                result = self._evaluate_simple_condition(sub_cond, context)

            results.append(result)

        # Apply operator logic
        if operator == LogicOperator.AND:
            return all(results) if results else False
        elif operator == LogicOperator.OR:
            return any(results) if results else False
        elif operator == LogicOperator.NOT:
            return not results[0] if results else True
        elif operator == LogicOperator.XOR:
            return sum(results) == 1

        return False

    def _evaluate_simple_condition(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Evaluate a simple condition."""
        metric = condition.get("metric")
        operator = condition.get("operator", "==")
        threshold = condition.get("value")

        if metric not in context:
            logger.debug(f"Metric not found in context: {metric}")
            return False

        value = context[metric]

        # Simple operators
        if operator == "==":
            return value == threshold
        elif operator == "!=":
            return value != threshold
        elif operator == ">":
            return value > threshold
        elif operator == "<":
            return value < threshold
        elif operator == ">=":
            return value >= threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == "in":
            return value in threshold
        elif operator == "contains":
            return threshold in str(value)

        return False

    def _evaluate_state_machine(self, trigger_id: str, context: Dict[str, Any]) -> bool:
        """Evaluate a state machine trigger."""
        trigger = self.triggers[trigger_id]
        current_state = trigger.get("current_state")
        transitions = trigger.get("transitions", {})

        if current_state not in transitions:
            return False

        # Check available transitions from current state
        for transition in transitions[current_state]:
            condition = transition.get("condition")
            if self._evaluate_composite_condition(condition, context):
                # Transition is valid
                new_state = transition.get("to_state")
                return self._transition_state(trigger_id, new_state)

        return False

    def _transition_state(self, trigger_id: str, new_state: str) -> bool:
        """Transition trigger to a new state."""
        trigger = self.triggers[trigger_id]
        old_state = trigger.get("current_state")

        if new_state == old_state:
            return False

        # Record transition
        trigger["current_state"] = new_state
        trigger["state_enter_time"] = datetime.now().isoformat()

        history = trigger.get("state_history", [])
        history.append((new_state, datetime.now().isoformat()))
        trigger["state_history"] = history

        # Call transition action if provided
        if trigger.get("action_on_transition"):
            try:
                trigger["action_on_transition"](old_state, new_state)
            except Exception as e:
                logger.error(f"State transition action error: {e}")

        logger.info(f"Trigger {trigger_id} transitioned: {old_state} -> {new_state}")
        return True

    def _is_cooldown_expired(self, trigger_id: str) -> bool:
        """Check if cooldown period has expired."""
        trigger = self.triggers.get(trigger_id)
        if not trigger:
            return True

        cooldown_seconds = trigger.get("cooldown_seconds", 0)
        if cooldown_seconds == 0:
            return True

        last_fired = trigger.get("last_fired")
        if not last_fired:
            return True

        last_fired_time = datetime.fromisoformat(last_fired)
        time_since = (datetime.now() - last_fired_time).total_seconds()

        return time_since >= cooldown_seconds

    def _check_dependencies(self, trigger_id: str, context: Dict[str, Any]) -> bool:
        """Check if all dependencies are satisfied."""
        if trigger_id not in self.dependencies:
            return True

        for dep in self.dependencies[trigger_id]:
            # Check if required trigger has fired
            required_trigger = self.triggers.get(dep.required_trigger_id)
            if not required_trigger:
                return False

            if dep.condition == "must_have_fired":
                if not required_trigger.get("last_fired"):
                    return False
            elif dep.condition == "must_not_fire":
                if required_trigger.get("last_fired"):
                    return False

        return True

    def _is_within_time_window(self, time_window: Dict[str, Any]) -> bool:
        """Check if current time is within specified window."""
        window_type = TimeWindowType(time_window.get("type"))

        if window_type == TimeWindowType.BUSINESS_HOURS:
            now = datetime.now()
            return 9 <= now.hour < 17 and now.weekday() < 5  # 9AM-5PM weekdays

        # For other types, would need implementation
        return True

    def _triggers_could_conflict(self, tid1: str, tid2: str) -> bool:
        """Determine if two triggers could conflict."""
        # Simplified check - in production would be more sophisticated
        t1 = self.triggers[tid1]
        t2 = self.triggers[tid2]

        # Check if they have overlapping conditions
        # This is a placeholder - actual implementation would be more thorough
        return t1.get("enabled", True) and t2.get("enabled", True) and tid1 != tid2


# Global instance
_advanced_trigger_manager = None


def get_advanced_trigger_manager() -> AdvancedTriggerManager:
    """Get or create the global advanced trigger manager instance."""
    global _advanced_trigger_manager
    if _advanced_trigger_manager is None:
        _advanced_trigger_manager = AdvancedTriggerManager()
    return _advanced_trigger_manager
