"""A metric created without a target is stored with its default one.

The target decides which tests a metric runs on, so every writer (the UI, the SDK, MCP
`create_metric`, the Architect) gets the same default, and the response says what it is.
"""

import json
import uuid

import pytest
from pydantic import ValidationError

from rhesis.backend.app.schemas.metric import Metric, MetricCreate, MetricUpdate


def _payload(**overrides):
    """A numeric metric that satisfies every other MetricCreate rule."""
    payload = dict(
        name="Faithfulness",
        evaluation_prompt="Judge whether the response is faithful to the context.",
        score_type="numeric",
        min_score=0.0,
        max_score=1.0,
        threshold=0.5,
    )
    payload.update(overrides)
    return payload


def _sdk_metric(*accepted):
    examples = {"sdk_connection": {"accepted_params": list(accepted)}}
    return _payload(class_name="my_check", evaluation_examples=json.dumps(examples))


@pytest.mark.unit
class TestDefaultTarget:
    def test_a_judge_judges_each_turn(self):
        assert MetricCreate(**_payload()).config == {"target": {"on": "turn"}}

    def test_a_conversational_metric_judges_the_conversation(self):
        metric = MetricCreate(**_payload(class_name="ConversationalJudge"))
        assert metric.config == {"target": {"on": "conversation"}}

    def test_a_trajectory_metric_judges_the_run(self):
        metric = MetricCreate(**_payload(class_name="ToolCallTrajectory"))
        assert metric.config == {"target": {"on": "run"}}

    def test_an_sdk_metric_by_what_its_function_reads(self):
        assert MetricCreate(**_sdk_metric("input", "output")).config["target"] == {"on": "turn"}
        assert MetricCreate(**_sdk_metric("trace")).config["target"] == {"on": "run"}

    def test_class_settings_are_kept_beside_it(self):
        metric = MetricCreate(
            **_payload(class_name="ToolCallTrajectory", config={"match": "exact"})
        )
        assert metric.config == {"match": "exact", "target": {"on": "run"}}

    def test_a_chosen_target_is_kept(self):
        metric = MetricCreate(**_payload(config={"target": {"on": "retrieval"}}))
        assert metric.config == {"target": {"on": "retrieval"}}

    def test_a_target_the_metric_cant_take_is_refused(self):
        with pytest.raises(ValidationError, match="can't judge 'turn'"):
            MetricCreate(**_payload(class_name="ConversationalJudge", config={"target": "turn"}))

    def test_a_reference_answer_rules_out_the_conversation(self):
        """A conversation has no expected response, so such a metric would never run."""
        with pytest.raises(ValidationError, match="can't judge 'conversation'"):
            MetricCreate(**_payload(ground_truth_required=True, config={"target": "conversation"}))

    def test_an_update_without_one_changes_nothing(self):
        assert MetricUpdate(name="Renamed").config is None

    def test_a_scope_is_refused_with_what_replaced_it(self):
        assert "metric_scope" not in MetricCreate.model_fields
        with pytest.raises(ValidationError, match="replaced by the target"):
            MetricCreate(**_payload(metric_scope=["Multi-Turn"]))
        with pytest.raises(ValidationError, match="replaced by the target"):
            MetricUpdate(metric_scope=["Multi-Turn"])


@pytest.mark.unit
class TestSupportedTargets:
    def _metric(self, **fields):
        return Metric(
            id=uuid.uuid4(),
            name="m",
            evaluation_prompt="p",
            score_type="numeric",
            **fields,
        )

    def test_a_judge_takes_every_target(self):
        assert self._metric().supported_targets[:2] == ["turn", "tool_call"]
        assert "conversation" in self._metric().supported_targets

    def test_a_reference_answer_rules_out_spans(self):
        supported = self._metric(ground_truth_required=True).supported_targets
        assert supported == ["turn", "run"]

    def test_a_conversational_metric(self):
        assert self._metric(class_name="GoalAchievementJudge").supported_targets == [
            "conversation",
            "run",
        ]
