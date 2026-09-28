"""Judges with the Jev decision model: categorical works, everything else refuses it."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from rhesis.sdk.metrics import UnsupportedModelType
from rhesis.sdk.metrics.providers.garak.detector_metric import GarakDetectorMetric
from rhesis.sdk.metrics.providers.native.categorical_judge import CategoricalJudge
from rhesis.sdk.metrics.providers.native.goal_achievement_judge import GoalAchievementJudge
from rhesis.sdk.metrics.providers.native.numeric_judge import NumericJudge
from rhesis.sdk.models import JevDecisionModel


@pytest.fixture
def jev():
    return JevDecisionModel(api_key="key")


@pytest.fixture
def metric(jev):
    return CategoricalJudge(
        name="tone",
        evaluation_prompt="Is the tone polite?",
        evaluation_steps="Read the reply.",
        categories=["polite", "rude"],
        passing_categories="polite",
        model=jev,
    )


def test_categorical_judge_asks_one_choice_question(metric):
    answers = {
        "score": {
            "type": "choice",
            "choice": "polite",
            "probabilities": {"polite": 0.93, "rude": 0.07},
            "confidence": 0.9,
        }
    }
    with patch.object(metric.model, "a_decide", new_callable=AsyncMock) as decide:
        decide.return_value = answers
        result = metric.evaluate(input="hi", output="Hello!", expected_output="A greeting")

    state, questions = decide.call_args.args
    assert state == {"input": "hi", "expected_output": "A greeting", "output_to_evaluate": "Hello!"}
    assert questions == {
        "score": {
            "type": "choice",
            "instructions": "Is the tone polite?\n\nRead the reply.",
            "criteria": {"polite": "polite", "rude": "rude"},
        }
    }
    assert result.score == "polite"
    assert result.details["is_successful"] is True
    assert result.details["reason"] == "Chose 'polite' (p=0.93)."
    assert result.details["probabilities"] == {"polite": 0.93, "rude": 0.07}
    assert json.loads(result.details["prompt"])["question"] == questions["score"]


def test_categorical_judge_still_sends_an_empty_output(metric):
    with patch.object(metric.model, "a_decide", new_callable=AsyncMock) as decide:
        decide.return_value = {"score": {"choice": "rude"}}
        metric.evaluate(input="hi", output="", expected_output="")
    state, _ = decide.call_args.args
    assert state == {"input": "hi", "output_to_evaluate": ""}


def test_categorical_judge_fails_a_non_passing_choice(metric):
    with patch.object(metric.model, "a_decide", new_callable=AsyncMock) as decide:
        decide.return_value = {"score": {"choice": "rude"}}
        result = metric.evaluate(input="hi", output="Go away", expected_output="x")
    assert result.score == "rude"
    assert result.details["reason"] == "Chose 'rude'."
    assert result.details["is_successful"] is False


def test_categorical_judge_reports_jev_failure(metric):
    with patch.object(metric.model, "a_decide", new_callable=AsyncMock) as decide:
        decide.side_effect = RuntimeError("upstream down")
        result = metric.evaluate(input="hi", output="Hello!", expected_output="x")
    assert result.score == "error"
    assert "upstream down" in result.details["error"]


def test_numeric_judge_refuses_jev(jev):
    with pytest.raises(UnsupportedModelType, match="a decision model"):
        NumericJudge(name="n", evaluation_prompt="p", min_score=0, max_score=1, model=jev)


def test_conversational_judge_refuses_jev(jev):
    with pytest.raises(UnsupportedModelType, match="a decision model"):
        GoalAchievementJudge(model=jev)


def test_switching_a_numeric_judge_to_jev_is_refused(jev):
    metric = NumericJudge(name="n", evaluation_prompt="p", min_score=0, max_score=1)
    with pytest.raises(UnsupportedModelType, match="a decision model"):
        metric.set_model(jev)


def test_garak_detectors_take_any_judge_model(jev):
    """Detectors never call the model, so a decision model as the run's judge is fine."""
    metric = GarakDetectorMetric(detector_class="mitigation.MitigationBypass", model=jev)
    assert metric.model is jev
