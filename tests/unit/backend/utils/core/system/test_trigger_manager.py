"""Unit tests for the unified trigger_manager module.

Covers TriggerManager (lightweight) and AdvancedTriggerManager (composite / state-machine).
"""

import pytest

from backend.utils.core.system.trigger_manager import (
    AdvancedTriggerManager,
    CompositeTriggerCondition,
    LogicOperator,
    TriggerEvaluator,
    TriggerManager,
    TriggerState,
    get_advanced_trigger_manager,
    get_trigger_manager,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_rule_eq():
    """A simple rule: score == 10."""
    return {
        "conditions": [{"metric": "score", "operator": "==", "value": 10}],
        "logic": "AND",
    }


@pytest.fixture
def simple_rule_gt():
    """A simple rule: score > 5."""
    return {
        "conditions": [{"metric": "score", "operator": ">", "value": 5}],
        "logic": "AND",
    }


@pytest.fixture
def multi_condition_or_rule():
    """OR rule: score > 5 OR label contains 'ok'."""
    return {
        "conditions": [
            {"metric": "score", "operator": ">", "value": 5},
            {"metric": "label", "operator": "contains", "value": "ok"},
        ],
        "logic": "OR",
    }


# ---------------------------------------------------------------------------
# TestTriggerEvaluator
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTriggerEvaluator:
    def test_equal_operator_matches(self):
        evaluator = TriggerEvaluator()
        result = evaluator.evaluate_condition(
            {"metric": "x", "operator": "==", "value": 42},
            {"x": 42},
        )
        assert result is True

    def test_equal_operator_no_match(self):
        evaluator = TriggerEvaluator()
        result = evaluator.evaluate_condition(
            {"metric": "x", "operator": "==", "value": 42},
            {"x": 0},
        )
        assert result is False

    def test_greater_than_operator(self):
        evaluator = TriggerEvaluator()
        assert evaluator.evaluate_condition({"metric": "v", "operator": ">", "value": 5}, {"v": 10}) is True
        assert evaluator.evaluate_condition({"metric": "v", "operator": ">", "value": 5}, {"v": 5}) is False

    def test_contains_operator_string(self):
        evaluator = TriggerEvaluator()
        result = evaluator.evaluate_condition(
            {"metric": "msg", "operator": "contains", "value": "error"},
            {"msg": "there was an error here"},
        )
        assert result is True

    def test_not_contains_operator(self):
        evaluator = TriggerEvaluator()
        result = evaluator.evaluate_condition(
            {"metric": "msg", "operator": "!contains", "value": "error"},
            {"msg": "all good"},
        )
        assert result is True

    def test_in_range_operator(self):
        evaluator = TriggerEvaluator()
        result = evaluator.evaluate_condition(
            {"metric": "score", "operator": "in_range", "min": 1, "max": 10},
            {"score": 5},
        )
        assert result is True

    def test_pattern_match_operator(self):
        evaluator = TriggerEvaluator()
        result = evaluator.evaluate_condition(
            {"metric": "filename", "operator": "matches", "value": r"\.py$"},
            {"filename": "app.py"},
        )
        assert result is True

    def test_in_operator(self):
        evaluator = TriggerEvaluator()
        result = evaluator.evaluate_condition(
            {"metric": "status", "operator": "in", "value": ["active", "pending"]},
            {"status": "active"},
        )
        assert result is True

    def test_missing_metric_returns_false(self):
        evaluator = TriggerEvaluator()
        result = evaluator.evaluate_condition(
            {"metric": "nonexistent", "operator": "==", "value": 1},
            {},
        )
        assert result is False

    def test_nested_dot_path(self):
        evaluator = TriggerEvaluator()
        result = evaluator.evaluate_condition(
            {"metric": "a.b", "operator": "==", "value": 99},
            {"a": {"b": 99}},
        )
        assert result is True

    def test_evaluate_rule_and_logic(self):
        evaluator = TriggerEvaluator()
        rule = {
            "conditions": [
                {"metric": "x", "operator": "==", "value": 1},
                {"metric": "y", "operator": "==", "value": 2},
            ],
            "logic": "AND",
        }
        assert evaluator.evaluate_rule(rule, {"x": 1, "y": 2}) is True
        assert evaluator.evaluate_rule(rule, {"x": 1, "y": 99}) is False

    def test_evaluate_rule_or_logic(self):
        evaluator = TriggerEvaluator()
        rule = {
            "conditions": [
                {"metric": "x", "operator": "==", "value": 1},
                {"metric": "y", "operator": "==", "value": 2},
            ],
            "logic": "OR",
        }
        assert evaluator.evaluate_rule(rule, {"x": 1, "y": 99}) is True
        assert evaluator.evaluate_rule(rule, {"x": 0, "y": 99}) is False

    def test_evaluate_rule_empty_conditions_returns_false(self):
        evaluator = TriggerEvaluator()
        assert evaluator.evaluate_rule({"conditions": [], "logic": "AND"}, {}) is False


# ---------------------------------------------------------------------------
# TestBasicTriggerEvaluation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBasicTriggerEvaluation:
    def test_add_trigger_returns_true(self, simple_rule_eq):
        tm = TriggerManager()
        assert tm.add_trigger("t1", simple_rule_eq, [{"action": "alert"}]) is True

    def test_duplicate_trigger_returns_false(self, simple_rule_eq):
        tm = TriggerManager()
        tm.add_trigger("t1", simple_rule_eq, [])
        assert tm.add_trigger("t1", simple_rule_eq, []) is False

    def test_evaluate_all_fires_matching_trigger(self, simple_rule_eq):
        tm = TriggerManager()
        tm.add_trigger("t1", simple_rule_eq, [{"action": "alert"}])
        result = tm.evaluate_all({"score": 10})
        assert len(result) == 1
        assert result[0]["trigger_id"] == "t1"

    def test_evaluate_all_does_not_fire_non_matching(self, simple_rule_eq):
        tm = TriggerManager()
        tm.add_trigger("t1", simple_rule_eq, [{"action": "alert"}])
        result = tm.evaluate_all({"score": 99})
        assert result == []

    def test_disabled_trigger_does_not_fire(self, simple_rule_eq):
        tm = TriggerManager()
        tm.add_trigger("t1", simple_rule_eq, [])
        tm.disable_trigger("t1")
        result = tm.evaluate_all({"score": 10})
        assert result == []

    def test_enable_disabled_trigger(self, simple_rule_eq):
        tm = TriggerManager()
        tm.add_trigger("t1", simple_rule_eq, [])
        tm.disable_trigger("t1")
        tm.enable_trigger("t1")
        result = tm.evaluate_all({"score": 10})
        assert len(result) == 1

    def test_remove_trigger(self, simple_rule_eq):
        tm = TriggerManager()
        tm.add_trigger("t1", simple_rule_eq, [])
        assert tm.remove_trigger("t1") is True
        assert "t1" not in tm.triggers

    def test_remove_nonexistent_trigger_returns_false(self):
        tm = TriggerManager()
        assert tm.remove_trigger("ghost") is False

    def test_or_rule_fires_on_partial_match(self, multi_condition_or_rule):
        tm = TriggerManager()
        tm.add_trigger("or_t", multi_condition_or_rule, [])
        # score <= 5 but label contains 'ok'
        result = tm.evaluate_all({"score": 1, "label": "ok"})
        assert len(result) == 1

    def test_to_dict_returns_all_triggers(self, simple_rule_eq):
        tm = TriggerManager()
        tm.add_trigger("t1", simple_rule_eq, [])
        d = tm.to_dict()
        assert "t1" in d


# ---------------------------------------------------------------------------
# TestCooldownLogic
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCooldownLogic:
    def test_cooldown_prevents_immediate_second_fire(self, simple_rule_eq):
        tm = TriggerManager()
        tm.add_trigger("t1", simple_rule_eq, [])
        ctx = {"score": 10}
        first = tm.evaluate_all(ctx, cooldown_minutes=5)
        second = tm.evaluate_all(ctx, cooldown_minutes=5)
        assert len(first) == 1
        assert len(second) == 0  # still in cooldown

    def test_zero_cooldown_always_fires(self, simple_rule_eq):
        tm = TriggerManager()
        tm.add_trigger("t1", simple_rule_eq, [])
        ctx = {"score": 10}
        first = tm.evaluate_all(ctx, cooldown_minutes=0)
        second = tm.evaluate_all(ctx, cooldown_minutes=0)
        assert len(first) == 1
        assert len(second) == 1  # no cooldown

    def test_advanced_cooldown_blocks_second_fire(self):
        atm = AdvancedTriggerManager()
        cond = CompositeTriggerCondition(
            id="c1",
            operator=LogicOperator.AND,
            sub_conditions=[{"metric": "x", "operator": "==", "value": 1}],
        )
        atm.register_composite_trigger("t1", "T1", cond, cooldown_seconds=60)
        ctx = {"x": 1}
        atm.fire_trigger("t1", ctx)
        # State should be COOLDOWN after firing
        assert atm.trigger_states["t1"] == TriggerState.COOLDOWN
        # evaluate_trigger should return False (in cooldown)
        assert atm.evaluate_trigger("t1", ctx) is False


# ---------------------------------------------------------------------------
# TestTriggerHistory
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTriggerHistory:
    def test_history_grows_after_fires(self, simple_rule_eq):
        tm = TriggerManager()
        tm.add_trigger("t1", simple_rule_eq, [])
        ctx = {"score": 10}
        tm.evaluate_all(ctx)
        tm.evaluate_all(ctx)  # second fire (no cooldown)
        assert len(tm.history) == 2

    def test_history_limit(self, simple_rule_eq):
        tm = TriggerManager()
        tm.add_trigger("t1", simple_rule_eq, [])
        ctx = {"score": 10}
        for _ in range(10):
            tm.evaluate_all(ctx)
        limited = tm.get_trigger_history(limit=3)
        assert len(limited) == 3

    def test_advanced_firing_history_recorded(self):
        atm = AdvancedTriggerManager()
        cond = CompositeTriggerCondition(
            id="c1",
            operator=LogicOperator.AND,
            sub_conditions=[{"metric": "x", "operator": "==", "value": 1}],
        )
        atm.register_composite_trigger("t1", "T1", cond)
        atm.fire_trigger("t1", {"x": 1})
        assert len(atm.firing_history) == 1
        assert atm.firing_history[0]["trigger_id"] == "t1"


# ---------------------------------------------------------------------------
# TestCompositeTriggers
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCompositeTriggers:
    def test_and_composite_true_when_all_match(self):
        atm = AdvancedTriggerManager()
        cond = CompositeTriggerCondition(
            id="c1",
            operator=LogicOperator.AND,
            sub_conditions=[
                {"metric": "a", "operator": "==", "value": 1},
                {"metric": "b", "operator": "==", "value": 2},
            ],
        )
        atm.register_composite_trigger("t1", "T1", cond)
        assert atm.evaluate_trigger("t1", {"a": 1, "b": 2}) is True

    def test_and_composite_false_when_one_fails(self):
        atm = AdvancedTriggerManager()
        cond = CompositeTriggerCondition(
            id="c1",
            operator=LogicOperator.AND,
            sub_conditions=[
                {"metric": "a", "operator": "==", "value": 1},
                {"metric": "b", "operator": "==", "value": 2},
            ],
        )
        atm.register_composite_trigger("t1", "T1", cond)
        assert atm.evaluate_trigger("t1", {"a": 1, "b": 99}) is False

    def test_or_composite_true_when_one_matches(self):
        atm = AdvancedTriggerManager()
        cond = CompositeTriggerCondition(
            id="c1",
            operator=LogicOperator.OR,
            sub_conditions=[
                {"metric": "a", "operator": "==", "value": 1},
                {"metric": "b", "operator": "==", "value": 2},
            ],
        )
        atm.register_composite_trigger("t1", "T1", cond)
        assert atm.evaluate_trigger("t1", {"a": 1, "b": 99}) is True

    def test_not_composite_inverts_single_condition(self):
        atm = AdvancedTriggerManager()
        cond = CompositeTriggerCondition(
            id="c1",
            operator=LogicOperator.NOT,
            sub_conditions=[
                {"metric": "a", "operator": "==", "value": 1},
            ],
        )
        atm.register_composite_trigger("t1", "T1", cond)
        assert atm.evaluate_trigger("t1", {"a": 99}) is True  # NOT(False) = True
        assert atm.evaluate_trigger("t1", {"a": 1}) is False  # NOT(True) = False

    def test_xor_composite_true_when_exactly_one_matches(self):
        atm = AdvancedTriggerManager()
        cond = CompositeTriggerCondition(
            id="c1",
            operator=LogicOperator.XOR,
            sub_conditions=[
                {"metric": "a", "operator": "==", "value": 1},
                {"metric": "b", "operator": "==", "value": 2},
            ],
        )
        atm.register_composite_trigger("t1", "T1", cond)
        assert atm.evaluate_trigger("t1", {"a": 1, "b": 99}) is True  # only a
        assert atm.evaluate_trigger("t1", {"a": 1, "b": 2}) is False  # both

    def test_trigger_not_found_returns_false(self):
        atm = AdvancedTriggerManager()
        assert atm.evaluate_trigger("ghost", {}) is False

    def test_disabled_trigger_not_evaluated(self):
        atm = AdvancedTriggerManager()
        cond = CompositeTriggerCondition(
            id="c1",
            operator=LogicOperator.AND,
            sub_conditions=[{"metric": "x", "operator": "==", "value": 1}],
        )
        atm.register_composite_trigger("t1", "T1", cond, enabled=False)
        assert atm.evaluate_trigger("t1", {"x": 1}) is False

    def test_fire_trigger_invokes_callback(self):
        results = []
        atm = AdvancedTriggerManager()
        cond = CompositeTriggerCondition(
            id="c1",
            operator=LogicOperator.AND,
            sub_conditions=[],
        )
        atm.register_composite_trigger("t1", "T1", cond, action_callback=lambda ctx: results.append(ctx))
        atm.fire_trigger("t1", {"x": 42})
        assert results == [{"x": 42}]

    def test_get_trigger_status(self):
        atm = AdvancedTriggerManager()
        cond = CompositeTriggerCondition(id="c1", operator=LogicOperator.AND, sub_conditions=[])
        atm.register_composite_trigger("t1", "My Trigger", cond)
        status = atm.get_trigger_status("t1")
        assert status["name"] == "My Trigger"
        assert "state" in status

    def test_register_trigger_dependency(self):
        atm = AdvancedTriggerManager()
        cond = CompositeTriggerCondition(id="c1", operator=LogicOperator.AND, sub_conditions=[])
        atm.register_composite_trigger("t1", "T1", cond)
        atm.register_composite_trigger("t2", "T2", cond)
        assert atm.add_trigger_dependency("t2", "t1") is True


# ---------------------------------------------------------------------------
# TestGlobalSingletons
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGlobalSingletons:
    def test_get_trigger_manager_returns_same_instance(self):
        # Reset for isolation
        import backend.utils.core.system.trigger_manager as tm_module

        tm_module._trigger_manager = None
        a = get_trigger_manager()
        b = get_trigger_manager()
        assert a is b

    def test_get_advanced_trigger_manager_returns_same_instance(self):
        import backend.utils.core.system.trigger_manager as tm_module

        tm_module._advanced_trigger_manager = None
        a = get_advanced_trigger_manager()
        b = get_advanced_trigger_manager()
        assert a is b
