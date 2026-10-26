"""Tests for the @metric decorator and signature validation."""

import pytest

from rhesis.sdk.connector.registry import METRIC_ALLOWED_PARAMS
from rhesis.sdk.decorators.metric import _validate_metric_signature


class TestMetricSignatureValidation:
    """Tests for _validate_metric_signature."""

    def test_input_and_output(self):
        def my_metric(input: str, output: str):
            pass

        params = _validate_metric_signature(my_metric)
        assert params == ["input", "output"]

    def test_full_signature(self):
        """Test metric with every allowed param."""

        def my_metric(input: str, output: str, trace, expectations):
            pass

        params = _validate_metric_signature(my_metric)
        assert set(params) == METRIC_ALLOWED_PARAMS

    def test_any_one_param_is_enough(self):
        def only_trace(trace):
            pass

        def only_output(output: str):
            pass

        assert _validate_metric_signature(only_trace) == ["trace"]
        assert _validate_metric_signature(only_output) == ["output"]

    def test_output_and_expectations(self):
        def my_metric(output: str, expectations):
            pass

        params = _validate_metric_signature(my_metric)
        assert set(params) == {"output", "expectations"}

    def test_declaring_context_names_trace_context(self):
        def groundedness(input: str, output: str, context: list):
            pass

        with pytest.raises(TypeError, match=r"'context'.*trace\.context"):
            _validate_metric_signature(groundedness)

    def test_declaring_expected_output_names_expectations(self):
        def exact(output: str, expected_output: str):
            pass

        with pytest.raises(TypeError, match=r"expectations\.response"):
            _validate_metric_signature(exact)

    def test_declaring_conversation_history_names_messages(self):
        def coherent(conversation_history):
            pass

        with pytest.raises(TypeError, match=r"trace\.messages\(\)"):
            _validate_metric_signature(coherent)

    def test_extra_params_raises(self):
        """Test that extra param names raise TypeError."""

        def bad_metric(input: str, output: str, custom_field: str):
            pass

        with pytest.raises(TypeError, match="invalid.*custom_field"):
            _validate_metric_signature(bad_metric)

    def test_no_params_raises(self):
        """Test that function with no params raises TypeError."""

        def bad_metric():
            pass

        with pytest.raises(TypeError, match="declares no parameters"):
            _validate_metric_signature(bad_metric)

    def test_param_order_preserved(self):
        """Test that parameter order is preserved in result."""

        def my_metric(output: str, input: str, trace):
            pass

        params = _validate_metric_signature(my_metric)
        assert params == ["output", "input", "trace"]


class TestMetricConstants:
    """Tests for metric parameter constants."""

    def test_allowed_params_are_the_four_evaluation_params(self):
        assert METRIC_ALLOWED_PARAMS == {"input", "output", "trace", "expectations"}


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


class TestMetricCalledDirectly:
    """A decorated function called from a script gets what the connector would give it."""

    @pytest.fixture
    def metric(self, monkeypatch):
        import importlib
        from unittest.mock import MagicMock

        # The package exports the decorator under the module's own name.
        metric_module = importlib.import_module("rhesis.sdk.decorators.metric")
        monkeypatch.setattr(metric_module, "is_client_disabled", lambda: False)
        monkeypatch.setattr(metric_module, "get_default_client", lambda: MagicMock())
        return metric_module.metric

    def test_a_string_becomes_the_expected_response(self, metric):
        @metric(score_type="binary")
        def exact_match(output: str, expectations) -> dict:
            return {"score": float(output == expectations.response)}

        assert exact_match(output="Paris", expectations="Paris") == {"score": 1.0}

    def test_shortcuts_build_the_trace(self, metric):
        @metric(score_type="binary")
        def looks_up_first(trace) -> dict:
            return {"score": float(trace.tool_calls[0]["name"] == "lookup_order")}

        calls = [{"name": "lookup_order"}, {"name": "issue_refund"}]
        result = looks_up_first(input="Refund 42", output="Done.", tool_calls=calls)
        assert result == {"score": 1.0}
