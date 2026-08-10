"""Scope filtering for metric configs in the batch execution path.

The batch path converts metrics to MetricConfig during prefetch, before it knows
each test's turn type, so `prepare_metric_configs` is called without a scope and
filtering has to happen at evaluation time instead.

Regression: nothing filtered on the multi-turn side, so `["Single-Turn"]` metrics
such as RagasFaithfulness ran against conversations. The multi-turn evaluator
passes `context=[]`, so they failed by construction, inflating the metric count
and depressing the reported pass rate.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from rhesis.backend.app.schemas.metric import MetricScope
from rhesis.backend.tasks.execution.evaluation import filter_configs_by_scope


class _Config:
    """Stands in for MetricConfig, which is what the batch path holds."""

    def __init__(self, name, metric_scope, class_name="SomeJudge"):
        self.name = name
        self.class_name = class_name
        self.metric_scope = metric_scope


@pytest.mark.unit
class TestFilterConfigsByScope:
    def test_single_turn_metric_excluded_from_multi_turn(self):
        """The reported bug: Faithfulness ran in a multi-turn test."""
        configs = [
            _Config("Faithfulness", ["Single-Turn"], "RagasFaithfulness"),
            _Config("Booking Momentum", ["Multi-Turn"], "ConversationalJudge"),
        ]

        kept = filter_configs_by_scope(configs, MetricScope.MULTI_TURN, "t1")

        assert [c.name for c in kept] == ["Booking Momentum"]

    def test_multi_turn_metric_excluded_from_single_turn(self):
        """The mirror case, which the old _is_multi_turn_only check did cover."""
        configs = [
            _Config("Faithfulness", ["Single-Turn"], "RagasFaithfulness"),
            _Config("Booking Momentum", ["Multi-Turn"], "ConversationalJudge"),
        ]

        kept = filter_configs_by_scope(configs, MetricScope.SINGLE_TURN, "t1")

        assert [c.name for c in kept] == ["Faithfulness"]

    @pytest.mark.parametrize(
        "scope", [MetricScope.SINGLE_TURN, MetricScope.MULTI_TURN]
    )
    def test_dual_scoped_metric_kept_for_both(self, scope):
        configs = [_Config("Response Conciseness", ["Single-Turn", "Multi-Turn"])]

        assert len(filter_configs_by_scope(configs, scope, "t1")) == 1

    @pytest.mark.parametrize("undeclared", [None, [], "Multi-Turn", 42])
    def test_undeclared_scope_is_dropped(self, undeclared):
        """Parity with the ORM-level filter: no declared scope means no evaluation.

        A bare string is deliberately included: it is mis-shaped data, not a
        one-element list, and must not be treated as a declared scope.
        """
        configs = [_Config("Unscoped", undeclared)]

        assert filter_configs_by_scope(configs, MetricScope.MULTI_TURN, "t1") == []
        assert filter_configs_by_scope(configs, MetricScope.SINGLE_TURN, "t1") == []

    def test_wrong_scope_logs_at_debug_not_info(self, caplog):
        """Explicitly-out-of-scope is routine — most behaviors mix scopes."""
        import logging

        configs = [_Config("Faithfulness", ["Single-Turn"], "RagasFaithfulness")]

        with caplog.at_level(logging.DEBUG, logger="rhesis.backend.tasks.execution.evaluation"):
            filter_configs_by_scope(configs, MetricScope.MULTI_TURN, "t1")

        levels = [r.levelname for r in caplog.records]
        assert "DEBUG" in levels
        assert "INFO" not in levels
        assert "WARNING" not in levels

    def test_no_declared_scope_logs_at_warning(self, caplog):
        """No scope at all should not exist for a real DB row (CHECK constraint),
        so seeing one is worth surfacing louder than the routine wrong-scope case."""
        import logging

        configs = [_Config("Unscoped", None, "SomeJudge")]

        with caplog.at_level(logging.DEBUG, logger="rhesis.backend.tasks.execution.evaluation"):
            filter_configs_by_scope(configs, MetricScope.MULTI_TURN, "t1")

        levels = [r.levelname for r in caplog.records]
        assert "WARNING" in levels
        assert not any("Unscoped" in r.message and r.levelname == "DEBUG" for r in caplog.records)

    def test_accepts_metric_scope_enums_not_just_strings(self):
        configs = [_Config("Enum scoped", [MetricScope.MULTI_TURN])]

        assert len(filter_configs_by_scope(configs, MetricScope.MULTI_TURN, "t1")) == 1
        assert filter_configs_by_scope(configs, MetricScope.SINGLE_TURN, "t1") == []

    def test_accepts_dict_configs(self):
        configs = [
            {"name": "Faithfulness", "metric_scope": ["Single-Turn"]},
            {"name": "State Consistency", "metric_scope": ["Multi-Turn"]},
        ]

        kept = filter_configs_by_scope(configs, MetricScope.MULTI_TURN, "t1")

        assert [c["name"] for c in kept] == ["State Consistency"]

    def test_empty_input_returns_empty(self):
        assert filter_configs_by_scope([], MetricScope.MULTI_TURN, "t1") == []

    def test_reproduces_the_reported_behavior_metric_set_helper(self):
        """The exact 10 metrics on the 'Booking Flow Completion' behavior.

        Multi-turn evaluation must keep 8 and drop the 2 single-turn-only ones,
        so the run scores out of 9 (8 plus Goal Achievement) rather than 11.
        """
        configs = [
            _Config("Answer Accuracy", ["Single-Turn"], "RagasAnswerAccuracy"),
            _Config("Faithfulness", ["Single-Turn"], "RagasFaithfulness"),
            _Config("Booking Momentum", ["Multi-Turn"]),
            _Config("Conversation Completeness", ["Multi-Turn"]),
            _Config("Progressive Clarification", ["Multi-Turn"]),
            _Config("Recovery Effectiveness", ["Multi-Turn"]),
            _Config("State Consistency", ["Multi-Turn"]),
            _Config("Capability Boundary Honesty", ["Single-Turn", "Multi-Turn"]),
            _Config("Failure Transparency", ["Single-Turn", "Multi-Turn"]),
            _Config("Response Conciseness", ["Single-Turn", "Multi-Turn"]),
        ]

        kept = {c.name for c in filter_configs_by_scope(configs, MetricScope.MULTI_TURN, "t1")}

        assert "Faithfulness" not in kept
        assert "Answer Accuracy" not in kept
        assert len(kept) == 8


@pytest.mark.unit
class TestMultiTurnEvaluatorAppliesScopeFilter:
    """Covers the wiring, not just the helper.

    Deleting the `filter_configs_by_scope` call in `_evaluate_multi_turn_metrics`
    passes every helper-level test above, so this asserts on what the evaluator
    actually receives.
    """

    @staticmethod
    def _conversation_output():
        return {
            "conversation_summary": [
                {
                    "penelope_message": "I need to check in for my flight",
                    "target_response": "I can only help with insurance questions.",
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_single_turn_metric_never_reaches_the_evaluator(self):
        from rhesis.backend.tasks.execution.batch.evaluation import (
            _evaluate_multi_turn_metrics,
        )

        configs = [
            _Config("Faithfulness", ["Single-Turn"], "RagasFaithfulness"),
            _Config("State Consistency", ["Multi-Turn"], "ConversationalJudge"),
        ]

        evaluator = MagicMock()
        future = asyncio.Future()
        future.set_result({"State Consistency": {"is_successful": True}})
        evaluator.a_evaluate = MagicMock(return_value=future)

        test = MagicMock()
        test.id = "test-1"
        test.test_configuration = {"goal": "check in for a flight"}

        await _evaluate_multi_turn_metrics(
            MagicMock(), evaluator, test, self._conversation_output(), configs
        )

        passed = evaluator.a_evaluate.call_args.kwargs["metrics"]
        assert [c.name for c in passed] == ["State Consistency"]

    @pytest.mark.asyncio
    async def test_no_evaluation_when_nothing_is_in_scope(self):
        """All-single-turn metrics must short-circuit, not call the evaluator."""
        from rhesis.backend.tasks.execution.batch.evaluation import (
            _evaluate_multi_turn_metrics,
        )

        configs = [_Config("Faithfulness", ["Single-Turn"], "RagasFaithfulness")]

        evaluator = MagicMock()
        evaluator.a_evaluate = MagicMock()

        test = MagicMock()
        test.id = "test-1"
        test.test_configuration = {"goal": "check in for a flight"}

        result = await _evaluate_multi_turn_metrics(
            MagicMock(), evaluator, test, self._conversation_output(), configs
        )

        assert result == {}
        evaluator.a_evaluate.assert_not_called()
