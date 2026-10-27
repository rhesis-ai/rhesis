"""Expected tool calls on tests, and the trajectory metric that judges them."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from rhesis.backend.app.schemas.metric import MetricCreate
from rhesis.backend.app.schemas.test import TestBulkCreate, TestCreate
from rhesis.backend.jobs.execution.evaluation import conversation_expectations
from rhesis.backend.jobs.execution.metric_plan import _cell_keys_for_test
from rhesis.backend.metrics.applicability import applicable, applies, needs_model
from rhesis.backend.metrics.evaluator import MetricEvaluator
from rhesis.backend.metrics.inputs import ResponseTrace
from rhesis.sdk.metrics import Expectations, MetricConfig

EXPECTED = [{"name": "lookup_order"}, {"name": "issue_refund", "arguments": {"order": 42}}]


def trajectory(name="Tool Call Trajectory", **settings):
    return MetricConfig(
        class_name="ToolCallTrajectory",
        backend="rhesis",
        name=name,
        score_type="numeric",
        parameters=settings or None,
    )


def judge():
    return MetricConfig(
        class_name="NumericJudge",
        backend="rhesis",
        name="helpfulness",
        score_type="numeric",
        parameters={"evaluation_prompt": "p", "min_score": 0, "max_score": 1, "threshold": 0.5},
    )


def response(*calls):
    return ResponseTrace(input="Refund order 42", output="Done.", tool_calls=list(calls))


@pytest.mark.unit
class TestApplicability:
    def test_a_trajectory_metric_needs_expected_tool_calls(self):
        assert not applies(trajectory(), None)
        assert not applies(trajectory(), Expectations(response="Done."))
        assert applies(trajectory(), Expectations(tool_calls=[]))

    def test_other_metrics_always_apply(self):
        assert applies(judge(), None)
        assert applies({"backend": "deepeval", "class_name": "DeepEvalFaithfulness"}, None)

    def test_a_metric_row_is_read_through_its_backend_type(self):
        row = SimpleNamespace(
            class_name="ToolCallTrajectory", backend_type=SimpleNamespace(type_value="rhesis")
        )

        assert not applies(row, None)

    def test_only_metrics_that_apply_are_kept(self):
        assert applicable([trajectory(), judge()], Expectations()) == [judge()]

    def test_a_trajectory_metric_needs_no_model(self):
        assert not needs_model(trajectory())
        assert needs_model(judge())


@pytest.mark.unit
class TestEvaluation:
    def test_the_metric_reads_the_responses_tool_calls(self):
        results = MetricEvaluator(require_model=True).evaluate(
            [trajectory()],
            response(
                {"name": "lookup_order", "arguments": {"order": 42}},
                {"name": "issue_refund", "arguments": {"order": 42, "reason": "late"}},
            ),
            Expectations(tool_calls=EXPECTED),
        )

        result = results["Tool Call Trajectory"]
        assert result["is_successful"] is True
        assert result["recall"] == 1.0
        assert result["actual_tool_calls"] == ["lookup_order", "issue_refund"]

    def test_stored_settings_reach_the_metric(self):
        results = MetricEvaluator().evaluate(
            [trajectory(match="exact")],
            response(
                {"name": "lookup_order", "arguments": {}},
                {"name": "log", "arguments": {}},
                {"name": "issue_refund", "arguments": {"order": 42}},
            ),
            Expectations(tool_calls=EXPECTED),
        )

        assert results["Tool Call Trajectory"]["is_successful"] is False

    def test_a_test_without_expected_calls_leaves_it_out(self):
        results = MetricEvaluator().evaluate(
            [trajectory()], response(), Expectations(response="Done.")
        )

        assert results == {}

    def test_production_traces_leave_it_out(self):
        assert MetricEvaluator().evaluate([trajectory()], response(), None) == {}

    def test_a_conversation_carries_its_expected_calls(self):
        expectations = conversation_expectations(
            {"goal": "Refund the order", "expected_tool_calls": EXPECTED}
        )

        assert [call.name for call in expectations.tool_calls] == ["lookup_order", "issue_refund"]


@pytest.mark.unit
class TestTheVerdictGrid:
    def _row(self, name, class_name):
        return SimpleNamespace(
            id=None,
            name=name,
            class_name=class_name,
            backend_type=SimpleNamespace(type_value="rhesis"),
        )

    def test_the_cell_is_not_applicable_without_expected_calls(self):
        keyed = [
            (
                "Tool Call Trajectory",
                self._row("Tool Call Trajectory", "ToolCallTrajectory"),
                False,
            ),
            ("helpfulness", self._row("helpfulness", "NumericJudge"), False),
        ]

        without = _cell_keys_for_test(keyed, False, "t1", Expectations())
        with_calls = _cell_keys_for_test(keyed, False, "t2", Expectations(tool_calls=EXPECTED))

        assert list(without.values()) == ["helpfulness"]
        assert sorted(with_calls.values()) == ["Tool Call Trajectory", "helpfulness"]


@pytest.mark.unit
class TestStoringExpectedCalls:
    def test_a_single_turn_test_keeps_its_expected_calls(self):
        test = TestCreate(
            prompt={"content": "Refund order 42"},
            test_configuration={"expected_tool_calls": EXPECTED},
        )

        assert test.test_configuration["expected_tool_calls"] == EXPECTED

    def test_a_multi_turn_test_keeps_its_expected_calls(self):
        test = TestCreate(
            test_configuration={"goal": "Refund the order", "expected_tool_calls": EXPECTED}
        )

        assert test.test_configuration["expected_tool_calls"] == EXPECTED

    @pytest.mark.parametrize(
        "calls",
        [[{"arguments": {}}], [{"name": ""}], [{"name": "x", "extra": 1}], "lookup_order"],
    )
    def test_malformed_calls_are_refused(self, calls):
        with pytest.raises(ValidationError, match="expected_tool_calls"):
            TestCreate(test_configuration={"expected_tool_calls": calls})

    def test_the_error_names_the_call_that_is_wrong(self):
        with pytest.raises(ValidationError, match=r"expected_tool_calls: 1 -> name"):
            TestCreate(
                test_configuration={"expected_tool_calls": [{"name": "a"}, {"arguments": {}}]}
            )

    def test_bulk_single_turn_tests_are_checked_too(self):
        with pytest.raises(ValidationError, match="expected_tool_calls"):
            TestBulkCreate(
                prompt={"content": "Hi"},
                requirement="r",
                category="c",
                topic="t",
                test_configuration={"expected_tool_calls": [{"arguments": {}}]},
            )


@pytest.mark.unit
class TestMetricSettings:
    def _metric(self, config):
        return MetricCreate(
            name="Tool Call Trajectory",
            evaluation_prompt="Compare.",
            score_type="numeric",
            min_score=0,
            max_score=1,
            threshold=1,
            class_name="ToolCallTrajectory",
            config=config,
        )

    def test_valid_settings_are_kept(self):
        assert self._metric({"match": "superset"}).config == {
            "match": "superset",
            "target": {"on": "run"},
        }

    @pytest.mark.parametrize("config", [{"match": "sometimes"}, {"order": "strict"}])
    def test_invalid_settings_are_refused(self, config):
        with pytest.raises(ValidationError):
            self._metric(config)
