"""Per-metric judge models are resolved during prefetch and reach the evaluator.

Metric evaluation in the batch path runs after ``session.close()``, so a metric
that names its own judge via ``parameters["model_id"]`` can only be resolved
while prefetch still holds the session. Before this was wired, the batch
evaluator was built with no ``db``, and every such override was dropped.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.tasks.execution.batch.context import (
    ExecutionContext,
    _resolve_metric_judge_models,
)
from rhesis.backend.tasks.execution.batch.runner import run_batch
from rhesis.sdk.metrics import MetricConfig

MODEL_A = "11111111-1111-1111-1111-111111111111"
MODEL_B = "22222222-2222-2222-2222-222222222222"


def _config(model_id, name="metric"):
    return MetricConfig(
        class_name="RhesisPromptMetric",
        backend="rhesis",
        name=name,
        parameters={"model_id": model_id} if model_id else {},
    )


def _make_execution_context(**overrides) -> ExecutionContext:
    defaults = dict(
        test_config=MagicMock(),
        test_run=MagicMock(),
        test_set=MagicMock(),
        endpoint=MagicMock(),
        organization_id="org-1",
        user_id="user-1",
        recovery_rounds=0,
    )
    defaults.update(overrides)
    return ExecutionContext(**defaults)


class TestResolveMetricJudgeModels:
    def test_resolves_each_distinct_model_once(self):
        """Deduped by model_id: a judge shared by many metrics is one lookup, not N."""
        session = MagicMock()
        configs = [_config(MODEL_A, "m1"), _config(MODEL_B, "m2"), _config(MODEL_A, "m3")]

        with patch(
            "rhesis.backend.metrics.strategies.local._resolve_metric_model",
            side_effect=lambda mid, *a: f"model-for-{mid}",
        ) as resolve:
            resolved = _resolve_metric_judge_models(session, "org-1", configs, {})

        assert resolved == {MODEL_A: f"model-for-{MODEL_A}", MODEL_B: f"model-for-{MODEL_B}"}
        assert resolve.call_count == 2

    def test_covers_per_test_configs_too(self):
        """Requirement-mapped metrics (P3) live in per_test_metric_configs, not the shared list."""
        session = MagicMock()

        with patch(
            "rhesis.backend.metrics.strategies.local._resolve_metric_model",
            side_effect=lambda mid, *a: f"model-for-{mid}",
        ):
            resolved = _resolve_metric_judge_models(
                session,
                "org-1",
                [],
                {"test-1": [_config(MODEL_A)], "test-2": [_config(MODEL_B)]},
            )

        assert set(resolved) == {MODEL_A, MODEL_B}

    def test_records_a_failed_resolution_rather_than_omitting_it(self):
        """The key must be present with None so the evaluator can tell this apart
        from an override it was simply never told about."""
        session = MagicMock()

        with patch(
            "rhesis.backend.metrics.strategies.local._resolve_metric_model",
            return_value=None,
        ):
            resolved = _resolve_metric_judge_models(session, "org-1", [_config(MODEL_A)], {})

        assert resolved == {MODEL_A: None}
        assert MODEL_A in resolved

    def test_metrics_without_an_override_add_nothing(self):
        session = MagicMock()

        with patch("rhesis.backend.metrics.strategies.local._resolve_metric_model") as resolve:
            resolved = _resolve_metric_judge_models(session, "org-1", [_config(None)], {})

        assert resolved == {}
        resolve.assert_not_called()


@pytest.mark.asyncio
async def test_the_batch_evaluator_receives_the_pre_resolved_judges():
    """Regression: MetricEvaluator was built with neither db nor pre-resolved
    models, so LocalStrategy's `if model_id and db` check dropped every override."""
    pre_resolved = {MODEL_A: MagicMock(name="judge")}
    ctx = _make_execution_context(
        execution_model=None,
        metric_configs=[_config(MODEL_A)],
        metric_models=pre_resolved,
        test_data={"t1": {"test": MagicMock()}},
    )

    with (
        patch(
            "rhesis.backend.tasks.execution.batch.runner.is_multi_turn_test",
            return_value=False,
        ),
        patch("rhesis.backend.metrics.evaluator.MetricEvaluator") as mock_evaluator,
        patch(
            "rhesis.backend.tasks.execution.batch.runner._run_gather",
            new=AsyncMock(return_value=[]),
        ),
    ):
        await run_batch(ctx, ["t1"])

    mock_evaluator.assert_called_once()
    assert mock_evaluator.call_args.kwargs["metric_models"] is pre_resolved
