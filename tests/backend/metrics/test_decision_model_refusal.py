"""A metric that can't judge with a decision model (Jev) errors visibly instead of vanishing."""

from unittest.mock import AsyncMock, patch

import pytest

from rhesis.backend.metrics.strategies.local import LocalStrategy, prepare_metrics
from rhesis.sdk.metrics import MetricConfig
from rhesis.sdk.models.providers.jev import JevDecisionModel


def _numeric(name="helpfulness"):
    return MetricConfig(
        class_name="NumericJudge",
        backend="rhesis",
        name=name,
        score_type="numeric",
        parameters={"evaluation_prompt": "p", "min_score": 0, "max_score": 10, "threshold": 5},
    )


@pytest.mark.unit
def test_prepare_metrics_reports_the_refusal():
    refused = []
    jev = JevDecisionModel(api_key="k")
    tasks = prepare_metrics([_numeric()], "expected", [], model=jev, refused=refused)

    assert tasks == []
    [result] = refused
    assert result["is_successful"] is False
    assert "a decision model" in result["reason"]


@pytest.mark.unit
def test_local_strategy_returns_the_refusal_as_an_error_result():
    strategy = LocalStrategy(model=JevDecisionModel(api_key="k"))
    results = strategy.evaluate([_numeric()], "in", "out", "expected", [])
    assert "a decision model" in results["helpfulness"]["reason"]


@pytest.mark.unit
def test_a_refusal_never_overwrites_a_result_with_the_same_name():
    categorical = MetricConfig(
        class_name="CategoricalJudge",
        backend="rhesis",
        name="helpfulness",
        score_type="categorical",
        parameters={
            "evaluation_prompt": "p",
            "categories": ["good", "bad"],
            "passing_categories": ["good"],
        },
    )
    answers = {"score": {"choice": "good", "probabilities": {"good": 0.9, "bad": 0.1}}}
    with patch.object(JevDecisionModel, "a_decide", new=AsyncMock(return_value=answers)):
        strategy = LocalStrategy(model=JevDecisionModel(api_key="k"))
        results = strategy.evaluate(
            [categorical, _numeric(), _numeric()], "in", "out", "expected", []
        )

    assert set(results) == {"helpfulness", "helpfulness_1", "helpfulness_2"}
    judged = [r for r in results.values() if "a decision model" not in r["reason"]]
    assert len(judged) == 1 and judged[0]["is_successful"] is True
