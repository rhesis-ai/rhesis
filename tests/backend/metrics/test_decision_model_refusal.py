"""A metric that can't judge with a decision model (Jev) errors visibly instead of vanishing."""

import pytest

from rhesis.backend.metrics.strategies.local import LocalStrategy, prepare_metrics
from rhesis.sdk.metrics import MetricConfig
from rhesis.sdk.models.providers.jev import JevDecisionModel


def _numeric():
    return MetricConfig(
        class_name="NumericJudge",
        backend="rhesis",
        name="helpfulness",
        score_type="numeric",
        parameters={"evaluation_prompt": "p", "min_score": 0, "max_score": 10, "threshold": 5},
    )


@pytest.mark.unit
def test_prepare_metrics_reports_the_refusal():
    refused = {}
    jev = JevDecisionModel(api_key="k")
    tasks = prepare_metrics([_numeric()], "expected", [], model=jev, refused=refused)

    assert tasks == []
    result = refused["helpfulness"]
    assert result["is_successful"] is False
    assert "a decision model" in result["reason"]


@pytest.mark.unit
def test_local_strategy_returns_the_refusal_as_an_error_result():
    strategy = LocalStrategy(model=JevDecisionModel(api_key="k"))
    results = strategy.evaluate([_numeric()], "in", "out", "expected", [])
    assert "a decision model" in results["helpfulness"]["reason"]
