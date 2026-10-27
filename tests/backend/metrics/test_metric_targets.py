"""A metric's target, stored in metric.config: what the backend evaluates it on."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from rhesis.backend.app.outcomes import Execution, Verdict, classify_metrics
from rhesis.backend.app.schemas.metric import (
    MetricCreate,
    MetricUpdate,
    check_metric_config,
    check_updated_config,
)
from rhesis.backend.app.services.test_run import _export_status
from rhesis.backend.metrics.evaluator import MetricEvaluator
from rhesis.backend.metrics.inputs import EvaluationInputs, ResponseTrace
from rhesis.backend.metrics.metric_config import evaluate_metric, metric_model_to_config
from rhesis.backend.metrics.strategies.connector import ConnectorStrategy
from rhesis.sdk.entities.trace import Trace
from rhesis.sdk.metrics import Expectations, MetricConfig
from rhesis.sdk.metrics.arguments import evaluation_arguments
from rhesis.sdk.metrics.base import BaseMetric, MetricResult

REFUND = {"name": "issue_refund", "arguments": {"order": 42}}
LOOKUP = {"name": "lookup_order", "arguments": {"order": 42}}

CONVERSATION = [
    {"role": "user", "content": "Refund order 42."},
    {"role": "assistant", "content": "Refunded.", "tool_calls": [LOOKUP, REFUND]},
    {"role": "user", "content": "Thanks."},
    {"role": "assistant", "content": "You're welcome.", "tool_calls": [LOOKUP]},
]


class ShortOutput(BaseMetric):
    """Passes when the output is at most ten characters."""

    def __init__(self):
        super().__init__(MetricConfig(name="short"), model=AsyncMock())

    def set_model(self, model):
        return model

    @evaluation_arguments
    def evaluate(self, input=None, output=None):
        return MetricResult(score=float(len(output)), details={"reason": f"{len(output)} chars"})


def trajectory(target):
    return MetricConfig(
        class_name="ToolCallTrajectory",
        backend="rhesis",
        name="Tool Call Trajectory",
        score_type="numeric",
        metric_scope=["Multi-Turn"],
        target=target,
    )


def response(**parts):
    return EvaluationInputs(trace=ResponseTrace(input="Refund order 42", output="Done.", **parts))


@pytest.mark.unit
class TestStoredTargets:
    def test_the_target_is_kept_apart_from_the_class_settings(self):
        row = MagicMock()
        fields = dict.fromkeys(
            ["id", "description", "evaluation_steps", "reasoning", "evaluation_examples"]
            + ["metric_scope", "backend_type", "model_id", "model", "min_score", "max_score"]
        )
        fields.update(
            name="Tool Call Trajectory",
            class_name="ToolCallTrajectory",
            evaluation_prompt=None,
            score_type="numeric",
            ground_truth_required=False,
            context_required=False,
            threshold=1,
            threshold_operator=">=",
            config={"match": "exact", "target": {"on": "run"}},
        )
        for key, value in fields.items():
            setattr(row, key, value)

        config = metric_model_to_config(row)

        assert config.target == {"on": "run"}
        assert config.parameters == {"match": "exact"}

    def test_a_valid_target_is_stored_without_its_defaults(self):
        config = check_metric_config(
            "ToolCallTrajectory", {"match": "exact", "target": {"on": "run", "aggregate": "all"}}
        )

        assert config == {"match": "exact", "target": {"on": "run"}}

    @pytest.mark.parametrize("on", ["turn", "tool_call"])
    def test_expected_tool_calls_are_not_held_against_a_turn_or_span(self, on):
        with pytest.raises(ValueError, match=f"can't judge '{on}'. Choices: The conversation"):
            check_metric_config("ToolCallTrajectory", {"target": {"on": on}})

    def test_a_metric_needing_a_reference_answer_takes_no_per_span_target(self):
        with pytest.raises(ValueError, match="can't judge 'retrieval'"):
            check_metric_config(None, {"target": "retrieval"}, ground_truth_required=True)

        assert check_metric_config(None, {"target": "turn"}, ground_truth_required=True)

    def test_a_deepeval_class_is_checked_too(self):
        with pytest.raises(ValueError, match="can't judge 'tool_call'"):
            check_metric_config("DeepEvalTurnRelevancy", {"target": "tool_call"})

    def test_an_sdk_metric_is_checked_by_the_parameters_it_declares(self):
        with pytest.raises(ValueError, match="can't judge 'run'"):
            check_metric_config(None, {"target": "run"}, accepted=["input", "output"])

        assert check_metric_config(None, {"target": "run"}, accepted=["trace"])

    def test_an_update_is_checked_against_what_the_stored_metric_says(self):
        stored = MagicMock(class_name=None, ground_truth_required=True, evaluation_examples=None)

        with pytest.raises(ValueError, match="can't judge 'tool_call'"):
            check_updated_config(MetricUpdate(config={"target": "tool_call"}), stored)

        update = MetricUpdate(ground_truth_required=False, config={"target": "tool_call"})
        assert check_updated_config(update, stored) == {"target": {"on": "tool_call"}}

    def test_a_malformed_target_names_the_problem(self):
        with pytest.raises(ValueError, match="Invalid target: on: Input should be"):
            check_metric_config(None, {"target": {"on": "spans"}})

    def test_a_custom_metric_takes_a_per_span_target(self):
        metric = MetricCreate(
            name="Refund policy",
            evaluation_prompt="Check the refund.",
            score_type="numeric",
            min_score=0,
            max_score=1,
            threshold=1,
            metric_scope=["Single-Turn"],
            config={"target": {"on": "tool_call", "name": "issue_refund"}},
        )

        assert metric.config == {"target": {"on": "tool_call", "name": "issue_refund"}}

    def test_a_create_with_a_bad_target_is_refused(self):
        with pytest.raises(ValidationError, match="min_share"):
            MetricCreate(
                name="m",
                evaluation_prompt="p",
                score_type="numeric",
                min_score=0,
                max_score=1,
                threshold=1,
                metric_scope=["Single-Turn"],
                config={"target": {"on": "tool_call", "aggregate": "share"}},
            )


@pytest.mark.unit
class TestEvaluatingTargets:
    def test_each_turn_of_a_conversation_is_judged_on_its_own(self):
        inputs = EvaluationInputs(trace=Trace.from_conversation(CONVERSATION))

        result = evaluate_metric(ShortOutput(), inputs, {"on": "turn"}, lambda r: r.score <= 10)

        assert (result.details["matched"], result.details["passed"]) == (2, 1)
        assert result.details["reason"] == "1 of 2 turns passed. #2: 15 chars"

    def test_a_target_the_metric_cannot_take_is_an_error_result(self):
        results = MetricEvaluator().evaluate(
            [trajectory({"on": "turn"})],
            Trace.from_conversation(CONVERSATION),
            Expectations(tool_calls=[{"name": "lookup_order"}]),
        )

        assert "can't judge 'turn'" in results["Tool Call Trajectory"]["error"]

    def test_the_whole_run_is_judged_once(self):
        results = MetricEvaluator().evaluate(
            [trajectory({"on": "run"})],
            Trace.from_conversation(CONVERSATION),
            Expectations(tool_calls=[{"name": "lookup_order"}, {"name": "issue_refund"}]),
        )

        assert results["Tool Call Trajectory"]["is_successful"] is True

    def test_without_a_target_the_conversation_is_judged_once(self):
        trace = Trace.from_conversation(CONVERSATION)

        results = MetricEvaluator().evaluate(
            [trajectory(None)],
            trace,
            Expectations(tool_calls=[{"name": "lookup_order"}, {"name": "issue_refund"}]),
        )

        assert results["Tool Call Trajectory"]["is_successful"] is True
        assert "spans" not in results["Tool Call Trajectory"]

    def test_each_reported_tool_call_is_judged(self):
        result = evaluate_metric(
            ShortOutput(), response(tool_calls=[{**LOOKUP, "output": "found"}, REFUND]), "tool_call"
        )

        assert result.details["matched"] == 2

    def test_a_target_matching_nothing_is_not_applicable(self):
        result = evaluate_metric(ShortOutput(), response(), {"on": "retrieval"})

        assert result.details["not_applicable"] is True
        assert "map context" in result.details["reason"]


class _Sender:
    def __init__(self):
        self.sent = []

    async def __call__(self, metric_run_id, metric_name, inputs):
        self.sent.append(inputs)
        return {"status": "success", "score": float(len(inputs["output"])), "details": {}}


def _sdk_metric(target, accepted=("input", "output", "expectations")):
    connection = {"sdk_connection": {"metric_name": "short_output", "accepted_params": accepted}}
    return MetricConfig(
        class_name="short_output",
        backend="sdk",
        name="short_output",
        threshold=3,
        threshold_operator="<=",
        evaluation_examples=json.dumps(connection),
        target=target,
    )


@pytest.mark.unit
class TestConnectorTargets:
    def test_each_tool_call_is_sent_on_its_own(self):
        sender = _Sender()
        inputs = response(tool_calls=[{**LOOKUP, "output": "found"}, {**REFUND, "output": "ok"}])

        results = asyncio.run(
            ConnectorStrategy(connector_metric_sender=sender).a_evaluate(
                [_sdk_metric({"on": "tool_call"})], inputs
            )
        )

        assert [sent["output"] for sent in sender.sent] == ["found", "ok"]
        result = results["short_output"]
        assert result["is_successful"] is False
        assert result["spans"][1]["name"] == "issue_refund"

    def test_the_sync_path_does_the_same(self):
        sender = _Sender()

        results = ConnectorStrategy(connector_metric_sender=sender).evaluate(
            [_sdk_metric({"on": "tool_call", "name": "issue_refund"})],
            response(tool_calls=[LOOKUP, {**REFUND, "output": "ok"}]),
        )

        assert [sent["output"] for sent in sender.sent] == ["ok"]
        assert results["short_output"]["is_successful"] is True

    def test_nothing_is_sent_when_nothing_matches(self):
        sender = _Sender()

        results = ConnectorStrategy(connector_metric_sender=sender).evaluate(
            [_sdk_metric({"on": "retrieval"})], response()
        )

        assert sender.sent == []
        assert results["short_output"]["not_applicable"] is True

    def test_a_target_the_function_cannot_take_is_an_error_result(self):
        sender = _Sender()

        results = ConnectorStrategy(connector_metric_sender=sender).evaluate(
            [_sdk_metric({"on": "run"})], response()
        )

        assert sender.sent == []
        assert "can't judge 'run'" in results["short_output"]["error"]

    def test_each_span_gets_the_goal_and_the_trace_dumped_once(self):
        sender = _Sender()
        inputs = EvaluationInputs(
            trace=ResponseTrace(input="Q", output="A", tool_calls=[LOOKUP, REFUND]),
            expectations=Expectations(response="Refunded.", goal="Refund it"),
        )

        ConnectorStrategy(connector_metric_sender=sender).evaluate(
            [_sdk_metric({"on": "tool_call"}, ("input", "output", "trace", "expectations"))],
            inputs,
        )

        first, second = sender.sent
        assert first["expectations"] == {"goal": "Refund it"}
        assert first["trace"] is second["trace"]


@pytest.mark.unit
class TestOutcomes:
    NA = {"is_successful": None, "not_applicable": True, "score": None}

    def test_a_metric_that_does_not_apply_has_no_say(self):
        assert classify_metrics({"a": {"is_successful": True}, "b": self.NA}) == (
            Execution.OK,
            Verdict.PASS,
        )

    def test_when_none_applies_the_result_is_inconclusive(self):
        assert classify_metrics({"b": self.NA}) == (Execution.OK, Verdict.INCONCLUSIVE)

    @pytest.mark.parametrize(
        ("result", "status"),
        [
            (NA, "Not applicable"),
            ({"is_successful": None}, "Inconclusive"),
            ({"is_successful": False, "error": "boom"}, "Error"),
            ({"is_successful": False}, "Fail"),
            ({"is_successful": True}, "Pass"),
        ],
    )
    def test_the_export_says_which_it_was(self, result, status):
        assert _export_status(result) == status
