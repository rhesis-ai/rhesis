"""Tests for the @metric decorator and signature validation."""

import pytest

from rhesis.sdk.connector.registry import (
    METRIC_ALLOWED_PARAMS,
    METRIC_OPTIONAL_PARAMS,
    METRIC_REQUIRED_PARAMS,
)
from rhesis.sdk.decorators.metric import _validate_metric_signature


class TestMetricSignatureValidation:
    """Tests for _validate_metric_signature."""

    def test_minimal_signature(self):
        """Test metric with only required params (input, output)."""

        def my_metric(input: str, output: str):
            pass

        params = _validate_metric_signature(my_metric)
        assert params == ["input", "output"]

    def test_full_signature(self):
        """Test metric with all four allowed params."""

        def my_metric(input: str, output: str, expected_output: str, context: list):
            pass

        params = _validate_metric_signature(my_metric)
        assert set(params) == METRIC_ALLOWED_PARAMS

    def test_with_expected_output_only(self):
        """Test metric with input, output, expected_output."""

        def my_metric(input: str, output: str, expected_output: str):
            pass

        params = _validate_metric_signature(my_metric)
        assert set(params) == {"input", "output", "expected_output"}

    def test_with_context_only(self):
        """Test metric with input, output, context."""

        def my_metric(input: str, output: str, context: list):
            pass

        params = _validate_metric_signature(my_metric)
        assert set(params) == {"input", "output", "context"}

    def test_missing_input_raises(self):
        """Test that missing 'input' param raises TypeError."""

        def bad_metric(output: str):
            pass

        with pytest.raises(TypeError, match="missing required.*input"):
            _validate_metric_signature(bad_metric)

    def test_missing_output_raises(self):
        """Test that missing 'output' param raises TypeError."""

        def bad_metric(input: str):
            pass

        with pytest.raises(TypeError, match="missing required.*output"):
            _validate_metric_signature(bad_metric)

    def test_missing_both_required_raises(self):
        """Test that missing both required params raises TypeError."""

        def bad_metric(expected_output: str):
            pass

        with pytest.raises(TypeError, match="missing required"):
            _validate_metric_signature(bad_metric)

    def test_extra_params_raises(self):
        """Test that extra param names raise TypeError."""

        def bad_metric(input: str, output: str, custom_field: str):
            pass

        with pytest.raises(TypeError, match="invalid.*custom_field"):
            _validate_metric_signature(bad_metric)

    def test_multiple_extra_params_raises(self):
        """Test that multiple extra param names are reported."""

        def bad_metric(input: str, output: str, foo: str, bar: int):
            pass

        with pytest.raises(TypeError, match="invalid"):
            _validate_metric_signature(bad_metric)

    def test_no_params_raises(self):
        """Test that function with no params raises TypeError."""

        def bad_metric():
            pass

        with pytest.raises(TypeError, match="missing required"):
            _validate_metric_signature(bad_metric)

    def test_param_order_preserved(self):
        """Test that parameter order is preserved in result."""

        def my_metric(output: str, input: str, context: list):
            pass

        params = _validate_metric_signature(my_metric)
        assert params == ["output", "input", "context"]


class TestMetricConstants:
    """Tests for metric parameter constants."""

    def test_required_params(self):
        assert METRIC_REQUIRED_PARAMS == {"input", "output"}

    def test_optional_params(self):
        assert METRIC_OPTIONAL_PARAMS == {"expected_output", "context"}

    def test_allowed_params_is_union(self):
        assert METRIC_ALLOWED_PARAMS == METRIC_REQUIRED_PARAMS | METRIC_OPTIONAL_PARAMS

    def test_allowed_has_four_params(self):
        assert len(METRIC_ALLOWED_PARAMS) == 4


class TestMetricDecoratorDisabled:
    """Tests for @metric when client is disabled."""

    def test_disabled_client_returns_original_function(self, monkeypatch):
        """When client is disabled, decorator returns the original function."""
        monkeypatch.setenv("RHESIS_CONNECTOR_DISABLED", "true")

        from rhesis.sdk.clients.rhesis import DisabledClient

        DisabledClient()

        from rhesis.sdk.decorators.metric import metric

        @metric()
        def my_metric(input: str, output: str) -> dict:
            return {"score": 0.9}

        assert my_metric.__name__ == "my_metric"
        result = my_metric(input="hello", output="world")
        assert result == {"score": 0.9}

    def test_disabled_client_register_metric_is_noop(self, monkeypatch):
        """DisabledClient.register_metric is a no-op."""
        monkeypatch.setenv("RHESIS_CONNECTOR_DISABLED", "true")

        from rhesis.sdk.clients.rhesis import DisabledClient

        client = DisabledClient()
        result = client.register_metric("test", lambda: None, {})
        assert result is None
