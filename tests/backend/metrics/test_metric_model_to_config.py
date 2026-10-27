"""
Unit tests for metric_model_to_config.

Covers the ORM model → MetricConfig conversion boundary, specifically that
fields present on the DB model are not silently dropped during conversion.
"""

from unittest.mock import MagicMock

import pytest

from rhesis.backend.metrics.metric_config import metric_model_to_config


def _make_metric(**overrides):
    """Minimal mock of a Metric ORM model suitable for metric_model_to_config."""
    m = MagicMock()
    m.id = "00000000-0000-0000-0000-000000000001"
    m.name = "Test Metric"
    m.class_name = "RhesisPromptMetric"
    m.description = "A test metric"
    m.evaluation_prompt = "Rate the quality"
    m.evaluation_steps = None
    m.reasoning = None
    m.evaluation_examples = None
    m.score_type = "numeric"
    m.ground_truth_required = False
    m.context_required = False
    m.backend_type = None
    m.threshold = 0.5
    m.threshold_operator = ">="
    m.min_score = 0.0
    m.max_score = 1.0
    m.model_id = None
    m.model = None
    for k, v in overrides.items():
        setattr(m, k, v)
    return m


class TestTargetPreservation:
    """The target, kept in metric.config, must survive the ORM → MetricConfig conversion."""

    def test_the_target_is_preserved(self):
        metric = _make_metric(config={"target": {"on": "conversation"}})
        assert metric_model_to_config(metric).target == {"on": "conversation"}

    def test_no_config_is_no_target(self):
        assert metric_model_to_config(_make_metric(config=None)).target is None


class TestOtherFieldsPreservation:
    """Sanity-check that unrelated fields are still copied correctly."""

    def test_name_is_preserved(self):
        metric = _make_metric(name="My Custom Metric")
        config = metric_model_to_config(metric)
        assert config.name == "My Custom Metric"

    def test_class_name_is_preserved(self):
        metric = _make_metric(class_name="NumericJudge")
        config = metric_model_to_config(metric)
        assert config.class_name == "NumericJudge"

    def test_threshold_is_preserved(self):
        metric = _make_metric(threshold=0.8)
        config = metric_model_to_config(metric)
        assert config.threshold == pytest.approx(0.8)
