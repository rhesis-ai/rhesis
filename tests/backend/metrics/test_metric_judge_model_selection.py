"""Tests for per-metric judge model (`model_id`) resolution.

A metric can name its own judge model via `parameters["model_id"]`. The batch
path evaluates metrics after its DB session has closed, so it cannot resolve
that id at evaluation time the way the sequential path does -- it has to be
pre-resolved during prefetch and handed over. These tests pin that the override
is honoured in both paths, and that any path which *cannot* honour it says so
instead of silently falling back to the default judge.
"""

import logging
from unittest.mock import MagicMock, patch

from rhesis.backend.metrics.strategies.local import (
    _select_metric_model,
    prepare_metrics,
)
from rhesis.sdk.metrics import MetricConfig

MODEL_ID = "11111111-1111-1111-1111-111111111111"


def _config_with_model_id(model_id=MODEL_ID, name="answer-relevancy"):
    return MetricConfig(
        class_name="RhesisPromptMetric",
        backend="rhesis",
        name=name,
        parameters={"model_id": model_id} if model_id else {},
    )


class TestSelectMetricModel:
    """The judge-model decision, including the paths that cannot honour an override."""

    def test_prefers_a_pre_resolved_model_over_the_session(self):
        pre_resolved = MagicMock(name="pre_resolved_model")
        db = MagicMock(name="db")

        with patch(
            "rhesis.backend.metrics.strategies.local._resolve_metric_model"
        ) as resolve_from_db:
            selected = _select_metric_model(
                MODEL_ID, db, "org-1", "answer-relevancy", {MODEL_ID: pre_resolved}
            )

        assert selected is pre_resolved
        resolve_from_db.assert_not_called()

    def test_resolves_from_the_session_when_nothing_was_pre_resolved(self):
        db = MagicMock(name="db")
        from_db = MagicMock(name="model_from_db")

        with patch(
            "rhesis.backend.metrics.strategies.local._resolve_metric_model",
            return_value=from_db,
        ) as resolve_from_db:
            selected = _select_metric_model(MODEL_ID, db, "org-1", "answer-relevancy", None)

        assert selected is from_db
        resolve_from_db.assert_called_once_with(MODEL_ID, db, "org-1", "answer-relevancy")

    def test_warns_when_the_override_cannot_be_resolved_at_all(self, caplog):
        """No session and no pre-resolution: the batch bug this suite exists for.

        Falling back to the default judge is acceptable; doing it silently is not,
        because the user configured a specific model and would never learn it was
        ignored.
        """
        with caplog.at_level(logging.WARNING):
            selected = _select_metric_model(MODEL_ID, None, "org-1", "answer-relevancy", None)

        assert selected is None
        assert any(
            MODEL_ID in record.message and record.levelno == logging.WARNING
            for record in caplog.records
        ), "expected a warning naming the model that could not be honoured"

    def test_warns_when_pre_resolution_was_attempted_and_failed(self, caplog):
        """A recorded None means "tried, failed" -- distinct from never attempted."""
        with caplog.at_level(logging.WARNING):
            selected = _select_metric_model(
                MODEL_ID, None, "org-1", "answer-relevancy", {MODEL_ID: None}
            )

        assert selected is None
        assert any(record.levelno == logging.WARNING for record in caplog.records)

    def test_a_failed_pre_resolution_does_not_fall_back_to_the_session(self):
        """Deliberate: the batch path's session is closed, so retrying it would raise."""
        db = MagicMock(name="db")

        with patch(
            "rhesis.backend.metrics.strategies.local._resolve_metric_model"
        ) as resolve_from_db:
            _select_metric_model(MODEL_ID, db, "org-1", "answer-relevancy", {MODEL_ID: None})

        resolve_from_db.assert_not_called()


class TestPrepareMetricsHonoursTheOverride:
    """End-to-end through prepare_metrics: the judge model reaches the metric."""

    def _create_with_captured_model(self):
        """Patch MetricFactory.create and report the `model` kwarg it received."""
        captured = {}

        def _create(backend, class_name, **kwargs):
            captured["model"] = kwargs.get("model")
            metric = MagicMock()
            metric.requires_ground_truth = False
            return metric

        return captured, _create

    def test_batch_path_uses_the_pre_resolved_judge(self):
        """Regression: with db=None this used to silently use the default model."""
        pre_resolved = MagicMock(name="pre_resolved_model")
        default_model = MagicMock(name="default_model")
        captured, create = self._create_with_captured_model()

        with patch("rhesis.sdk.metrics.MetricFactory.create", side_effect=create):
            tasks = prepare_metrics(
                [_config_with_model_id()],
                expected_output=None,
                model=default_model,
                db=None,
                metric_models={MODEL_ID: pre_resolved},
            )

        assert len(tasks) == 1
        assert captured["model"] is pre_resolved
        assert captured["model"] is not default_model

    def test_falls_back_to_the_default_judge_when_the_override_is_unresolvable(self):
        default_model = MagicMock(name="default_model")
        captured, create = self._create_with_captured_model()

        with patch("rhesis.sdk.metrics.MetricFactory.create", side_effect=create):
            prepare_metrics(
                [_config_with_model_id()],
                expected_output=None,
                model=default_model,
                db=None,
                metric_models={MODEL_ID: None},
            )

        assert captured["model"] is default_model

    def test_a_metric_without_an_override_uses_the_default_judge(self):
        default_model = MagicMock(name="default_model")
        captured, create = self._create_with_captured_model()

        with patch("rhesis.sdk.metrics.MetricFactory.create", side_effect=create):
            prepare_metrics(
                [_config_with_model_id(model_id=None)],
                expected_output=None,
                model=default_model,
                db=None,
                metric_models={},
            )

        assert captured["model"] is default_model
