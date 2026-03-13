"""
Unit tests for MetricResultBuilder - success, error, and timeout result factories.
"""

from rhesis.backend.metrics.result_builder import MetricResultBuilder


class TestMetricResultBuilderSuccess:
    """Tests for MetricResultBuilder.success()."""

    def test_success_returns_expected_dict(self):
        """Success result includes required fields and strips None optionals."""
        d = MetricResultBuilder.success(
            score=0.85,
            reason="Score: 0.85",
            is_successful=True,
            backend="rhesis",
            name="MyMetric",
            class_name="NumericJudge",
        )
        assert d["score"] == 0.85
        assert d["reason"] == "Score: 0.85"
        assert d["is_successful"] is True
        assert d["backend"] == "rhesis"
        assert d["name"] == "MyMetric"
        assert d["class_name"] == "NumericJudge"
        assert "error" not in d
        assert "error_type" not in d

    def test_success_with_threshold(self):
        """Success result can include threshold."""
        d = MetricResultBuilder.success(
            score=0.9,
            reason="Pass",
            is_successful=True,
            backend="deepeval",
            name="Faithfulness",
            class_name="DeepEvalFaithfulness",
            threshold=0.7,
        )
        assert d["threshold"] == 0.7

    def test_success_with_reference_score(self):
        """Success result can include reference_score for categorical metrics."""
        d = MetricResultBuilder.success(
            score="True",
            reason="Match",
            is_successful=True,
            backend="rhesis",
            name="CatJudge",
            class_name="CategoricalJudge",
            reference_score="True",
        )
        assert d["reference_score"] == "True"
        assert "threshold" not in d

    def test_success_with_duration_ms(self):
        """Success result can include duration_ms (e.g. from SDK)."""
        d = MetricResultBuilder.success(
            score=1.0,
            reason="OK",
            is_successful=True,
            backend="sdk",
            name="SDKMetric",
            class_name="CustomMetric",
            duration_ms=150.5,
        )
        assert d["duration_ms"] == 150.5


class TestMetricResultBuilderError:
    """Tests for MetricResultBuilder.error()."""

    def test_error_returns_expected_dict(self):
        """Error result has score=0, is_successful=False and error fields."""
        d = MetricResultBuilder.error(
            reason="Evaluation failed: connection error",
            backend="rhesis",
            name="MyMetric",
            class_name="NumericJudge",
            error="connection error",
            error_type="ConnectionError",
        )
        assert d["score"] == 0.0
        assert d["reason"] == "Evaluation failed: connection error"
        assert d["is_successful"] is False
        assert d["backend"] == "rhesis"
        assert d["name"] == "MyMetric"
        assert d["class_name"] == "NumericJudge"
        assert d["error"] == "connection error"
        assert d["error_type"] == "ConnectionError"

    def test_error_with_duration_ms(self):
        """Error result can include duration_ms (e.g. from SDK)."""
        d = MetricResultBuilder.error(
            reason="SDK metric error",
            backend="sdk",
            name="SDKMetric",
            class_name="Unknown",
            error="timeout",
            duration_ms=60000.0,
        )
        assert d["duration_ms"] == 60000.0


class TestMetricResultBuilderTimeout:
    """Tests for MetricResultBuilder.timeout()."""

    def test_timeout_returns_expected_dict(self):
        """Timeout result has timeout reason and error_type TimeoutError."""
        d = MetricResultBuilder.timeout(
            backend="rhesis",
            name="SlowMetric",
            class_name="NumericJudge",
            timeout_seconds=600,
        )
        assert d["score"] == 0.0
        assert "Metric evaluation timed out after 600s" in d["reason"]
        assert d["is_successful"] is False
        assert d["backend"] == "rhesis"
        assert d["name"] == "SlowMetric"
        assert d["class_name"] == "NumericJudge"
        assert d["error"] == "Timeout"
        assert d["error_type"] == "TimeoutError"

    def test_timeout_custom_seconds(self):
        """Timeout message uses provided timeout_seconds."""
        d = MetricResultBuilder.timeout(
            backend="x",
            name="n",
            class_name="C",
            timeout_seconds=120,
        )
        assert "120s" in d["reason"]


class TestMetricResultBuilderToDict:
    """Tests for to_dict() None-stripping."""

    def test_to_dict_strips_none_fields(self):
        """Optional None fields are omitted from the dict."""
        b = MetricResultBuilder(
            score=0.0,
            reason="err",
            is_successful=False,
            backend="x",
            name="n",
            class_name="C",
            description="",
            threshold=None,
            reference_score=None,
            error_message="err",
            error_type=None,
            duration_ms=None,
        )
        d = b.to_dict()
        assert "threshold" not in d
        assert "reference_score" not in d
        assert "error_type" not in d
        assert "duration_ms" not in d
        assert d["error"] == "err"
