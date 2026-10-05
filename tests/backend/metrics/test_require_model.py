"""A test run never lets a metric judge with a model the SDK built for itself.

Without a model, the SDK metric builds its own default: not the model the run chose,
and its usage carries no stamp. Runs ask for an error result instead.
"""

from unittest.mock import patch

import pytest

from rhesis.backend.metrics.strategies.local import (
    NO_JUDGE_MODEL_REASON,
    LocalStrategy,
    prepare_metrics,
)
from rhesis.sdk.metrics import MetricConfig


def _numeric(name="helpfulness"):
    return MetricConfig(
        class_name="NumericJudge",
        backend="rhesis",
        name=name,
        score_type="numeric",
        parameters={"evaluation_prompt": "p", "min_score": 0, "max_score": 10, "threshold": 5},
    )


@pytest.mark.unit
def test_a_metric_without_a_model_is_refused_before_the_sdk_builds_one():
    refused = []
    with patch("rhesis.sdk.metrics.MetricFactory.create") as create:
        tasks = prepare_metrics(
            [_numeric()], "expected", [], model=None, refused=refused, require_model=True
        )

    create.assert_not_called()
    assert tasks == []
    [result] = refused
    assert result["is_successful"] is False
    assert result["reason"] == NO_JUDGE_MODEL_REASON
    assert result["error_type"] == "NoJudgeModel"


@pytest.mark.unit
def test_the_run_sees_the_metric_as_errored():
    strategy = LocalStrategy(model=None, require_model=True)

    results = strategy.evaluate([_numeric()], "in", "out", "expected", [])

    assert results["helpfulness"]["reason"] == NO_JUDGE_MODEL_REASON


@pytest.mark.unit
def test_a_metric_with_a_model_is_unaffected():
    model = object()
    with patch("rhesis.sdk.metrics.MetricFactory.create") as create:
        tasks = prepare_metrics([_numeric()], "expected", [], model=model, require_model=True)

    assert len(tasks) == 1
    assert create.call_args.kwargs["model"] is model


@pytest.mark.unit
def test_other_callers_keep_the_old_behaviour():
    """Only test runs opt in."""
    with patch("rhesis.sdk.metrics.MetricFactory.create") as create:
        tasks = prepare_metrics([_numeric()], "expected", [], model=None)

    assert len(tasks) == 1
    assert "model" not in create.call_args.kwargs
