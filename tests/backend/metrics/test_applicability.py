"""Which metrics apply to a test, by their target: what replaced metric_scope."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from rhesis.backend.jobs.execution.evaluation import conversation_trace
from rhesis.backend.metrics.applicability import applicable, applies, fits, metric_target
from rhesis.backend.metrics.evaluator import MetricEvaluator
from rhesis.backend.metrics.inputs import ResponseTrace
from rhesis.sdk.metrics import Expectations, MetricConfig

CALLS = [{"name": "lookup_order"}]


def config(class_name="NumericJudge", target=None, **fields):
    return MetricConfig(
        class_name=class_name,
        backend="rhesis",
        name=fields.pop("name", class_name),
        score_type="numeric",
        target=target,
        **fields,
    )


def conversation(turns=2):
    return conversation_trace(
        [
            {"penelope_message": f"Question {i}", "target_response": f"Answer {i}"}
            for i in range(turns)
        ]
    )


@pytest.mark.unit
class TestMetricTarget:
    def test_the_stored_target_wins(self):
        assert metric_target(config(target="tool_call")) == "tool_call"
        assert metric_target({"config": {"target": {"on": "run"}}}) == "run"

    def test_without_one_the_class_default(self):
        assert metric_target(config()) == "turn"
        assert metric_target(config("ConversationalJudge")) == "conversation"
        assert metric_target({"class_name": "DeepEvalTurnRelevancy"}) == "conversation"
        assert metric_target(config("ToolCallTrajectory")) == "run"

    def test_unknown_when_neither_is_known(self):
        assert metric_target({"class_name": "my_code_metric", "backend": "sdk"}) is None
        assert metric_target(MagicMock()) is None


@pytest.mark.unit
class TestFits:
    def test_a_conversation_target_needs_a_conversation(self):
        assert not fits(config("ConversationalJudge"), conversation=False)
        assert fits(config("ConversationalJudge"), conversation=True)

    @pytest.mark.parametrize("target", [None, "turn", "run", "tool_call"])
    def test_other_targets_judge_both(self, target):
        assert fits(config(target=target), conversation=False)
        assert fits(config(target=target), conversation=True)

    def test_a_conversation_has_no_reference_answer(self):
        reference = config(requires_ground_truth=True)

        assert fits(reference, conversation=False)
        assert not fits(reference, conversation=True)
        assert not fits(SimpleNamespace(class_name="X", requires_ground_truth=True), True)

    def test_a_class_needing_a_reference_answer_counts_whatever_its_row_says(self):
        """DeepEval's contextual recall compares with one; its seeded row says it doesn't."""
        row = {
            "backend": "deepeval",
            "class_name": "DeepEvalContextualRecall",
            "ground_truth_required": False,
        }

        assert fits(row, conversation=False)
        assert not fits(row, conversation=True)

    def test_a_mock_is_no_reference_metric(self):
        assert fits(MagicMock(), conversation=True)

    def test_expectations_still_count(self):
        trajectory = config("ToolCallTrajectory")

        assert not applies(trajectory, None, conversation=True)
        assert applies(trajectory, Expectations(tool_calls=CALLS), conversation=True)

    def test_applicable_keeps_what_fits(self):
        turn, whole = config(name="turn"), config("ConversationalJudge", name="whole")

        assert applicable([turn, whole], None) == [turn]
        assert applicable([turn, whole], None, conversation=True) == [turn, whole]


@pytest.mark.unit
class TestTheEvaluatorLeavesOut:
    def _trajectory(self, target):
        return config("ToolCallTrajectory", target=target, name="Trajectory")

    def test_a_conversation_metric_on_one_response(self):
        response = ResponseTrace(input="Hi", output="Hello", tool_calls=CALLS)

        results = MetricEvaluator().evaluate(
            [self._trajectory("conversation")], response, Expectations(tool_calls=CALLS)
        )

        assert results == {}

    def test_not_on_a_conversation(self):
        results = MetricEvaluator().evaluate(
            [self._trajectory("conversation")], conversation(), Expectations(tool_calls=[])
        )

        assert results["Trajectory"]["is_successful"] is True

    def test_a_one_turn_conversation_is_still_one(self):
        results = MetricEvaluator().evaluate(
            [self._trajectory("conversation")], conversation(turns=1), Expectations(tool_calls=[])
        )

        assert "Trajectory" in results

    def test_unless_told_it_is_one(self):
        response = ResponseTrace(input="Hi", output="Hello")

        results = MetricEvaluator().evaluate(
            [self._trajectory("conversation")],
            response,
            Expectations(tool_calls=[]),
            conversation=True,
        )

        assert "Trajectory" in results
