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
    m.metric_scope = None
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


class TestMetricScopePreservation:
    """metric_scope must survive the ORM → MetricConfig conversion."""

    def test_single_turn_scope_is_preserved(self):
        metric = _make_metric(metric_scope=["Single-Turn"])
        config = metric_model_to_config(metric)
        assert config.metric_scope is not None
        assert len(config.metric_scope) == 1
        assert "Single-Turn" in [
            s.value if hasattr(s, "value") else s for s in config.metric_scope
        ]

    def test_multi_turn_scope_is_preserved(self):
        metric = _make_metric(metric_scope=["Multi-Turn"])
        config = metric_model_to_config(metric)
        assert config.metric_scope is not None
        assert len(config.metric_scope) == 1
        assert "Multi-Turn" in [
            s.value if hasattr(s, "value") else s for s in config.metric_scope
        ]

    def test_multi_scope_values_are_preserved(self):
        metric = _make_metric(metric_scope=["Single-Turn", "Multi-Turn"])
        config = metric_model_to_config(metric)
        assert config.metric_scope is not None
        scope_values = [s.value if hasattr(s, "value") else s for s in config.metric_scope]
        assert "Single-Turn" in scope_values
        assert "Multi-Turn" in scope_values

    def test_none_scope_is_preserved(self):
        metric = _make_metric(metric_scope=None)
        config = metric_model_to_config(metric)
        assert config.metric_scope is None

    def test_missing_scope_attribute_does_not_raise(self):
        """getattr fallback must not raise when the column is absent."""
        metric = _make_metric()
        del metric.metric_scope  # simulate column not present
        config = metric_model_to_config(metric)
        assert config.metric_scope is None


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
