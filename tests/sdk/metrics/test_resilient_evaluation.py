"""Tests for the @resilient_evaluation decorator."""

import asyncio

import pytest

from rhesis.sdk.metrics.base import BaseMetric, MetricConfig, MetricResult
from rhesis.sdk.metrics.utils import _inconclusive_result, resilient_evaluation


class _StubMetric(BaseMetric):
    """Minimal concrete metric for testing decorators."""

    def __init__(self, name="test_metric"):
        config = MetricConfig(name=name)
        super().__init__(config=config)

    def evaluate(self, **kwargs):
        pass


class TestInconclusiveResult:
    def test_returns_metric_result(self):
        result = _inconclusive_result("my_metric", ValueError("boom"))
        assert isinstance(result, MetricResult)

    def test_score_is_none(self):
        result = _inconclusive_result("my_metric", ValueError("boom"))
        assert result.score is None

    def test_is_successful_is_none(self):
        result = _inconclusive_result("m", ValueError("x"))
        assert result.details["is_successful"] is None

    def test_inconclusive_flag(self):
        result = _inconclusive_result("m", ValueError("x"))
        assert result.details["inconclusive"] is True

    def test_error_type_captured(self):
        result = _inconclusive_result("m", TypeError("bad type"))
        assert result.details["error_type"] == "TypeError"

    def test_metric_name_in_reason(self):
        result = _inconclusive_result("answer_accuracy", RuntimeError(""))
        assert "answer_accuracy" in result.details["reason"]

    def test_no_raw_exception_message_in_details(self):
        secret = "raw LLM output with PII"
        result = _inconclusive_result("m", ValueError(secret))
        assert secret not in result.details.get("reason", "")
        assert "error" not in result.details


class TestResilientEvaluationAsync:
    def test_passes_through_on_success(self):
        expected = MetricResult(score=0.85, details={"is_successful": True})

        class M(_StubMetric):
            @resilient_evaluation
            async def a_evaluate(self, **kwargs):
                return expected

        result = asyncio.get_event_loop().run_until_complete(M().a_evaluate())
        assert result is expected

    def test_catches_exception_returns_inconclusive(self):
        class M(_StubMetric):
            @resilient_evaluation
            async def a_evaluate(self, **kwargs):
                raise RuntimeError("model output parse failed")

        result = asyncio.get_event_loop().run_until_complete(M().a_evaluate())
        assert result.score is None
        assert result.details["inconclusive"] is True
        assert result.details["is_successful"] is None
        assert result.details["error_type"] == "RuntimeError"

    def test_uses_metric_name_attribute(self):
        class M(_StubMetric):
            @resilient_evaluation
            async def a_evaluate(self, **kwargs):
                raise ValueError("x")

        m = M(name="faithfulness")
        result = asyncio.get_event_loop().run_until_complete(m.a_evaluate())
        assert "faithfulness" in result.details["reason"]

    def test_propagates_args_to_wrapped_function(self):
        class M(_StubMetric):
            @resilient_evaluation
            async def a_evaluate(self, input, output):
                return MetricResult(score=1.0, details={"input": input, "output": output})

        result = asyncio.get_event_loop().run_until_complete(M().a_evaluate("hello", "world"))
        assert result.details["input"] == "hello"
        assert result.details["output"] == "world"


class TestResilientEvaluationSync:
    def test_passes_through_on_success(self):
        expected = MetricResult(score=0.5, details={"is_successful": True})

        class M(_StubMetric):
            @resilient_evaluation
            def evaluate(self, **kwargs):
                return expected

        result = M().evaluate()
        assert result is expected

    def test_catches_exception_returns_inconclusive(self):
        class M(_StubMetric):
            @resilient_evaluation
            def evaluate(self, **kwargs):
                raise RuntimeError("parse error")

        result = M().evaluate()
        assert result.score is None
        assert result.details["inconclusive"] is True
        assert result.details["is_successful"] is None
        assert result.details["error_type"] == "RuntimeError"

    def test_catches_all_exception_types(self):
        for exc_cls in (ValueError, TypeError, KeyError, AttributeError):

            class M(_StubMetric):
                _exc = exc_cls

                @resilient_evaluation
                def evaluate(self, **kwargs):
                    raise self._exc("fail")

            result = M().evaluate()
            assert result.details["inconclusive"] is True
            assert result.details["error_type"] == exc_cls.__name__


class TestResilientEvaluationPassthrough:
    """Transient/infra exceptions must propagate so retry mechanisms work."""

    def test_reraises_connection_error_sync(self):
        class M(_StubMetric):
            @resilient_evaluation
            def evaluate(self, **kwargs):
                raise ConnectionError("connection refused")

        with pytest.raises(ConnectionError):
            M().evaluate()

    def test_reraises_timeout_error_sync(self):
        class M(_StubMetric):
            @resilient_evaluation
            def evaluate(self, **kwargs):
                raise TimeoutError("timed out")

        with pytest.raises(TimeoutError):
            M().evaluate()

    def test_reraises_os_error_sync(self):
        class M(_StubMetric):
            @resilient_evaluation
            def evaluate(self, **kwargs):
                raise OSError("network unreachable")

        with pytest.raises(OSError):
            M().evaluate()

    def test_reraises_keyboard_interrupt_sync(self):
        class M(_StubMetric):
            @resilient_evaluation
            def evaluate(self, **kwargs):
                raise KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            M().evaluate()

    def test_reraises_connection_error_async(self):
        class M(_StubMetric):
            @resilient_evaluation
            async def a_evaluate(self, **kwargs):
                raise ConnectionError("connection refused")

        with pytest.raises(ConnectionError):
            asyncio.get_event_loop().run_until_complete(M().a_evaluate())

    def test_reraises_timeout_error_async(self):
        class M(_StubMetric):
            @resilient_evaluation
            async def a_evaluate(self, **kwargs):
                raise TimeoutError("timed out")

        with pytest.raises(TimeoutError):
            asyncio.get_event_loop().run_until_complete(M().a_evaluate())

    def test_reraises_os_error_async(self):
        class M(_StubMetric):
            @resilient_evaluation
            async def a_evaluate(self, **kwargs):
                raise OSError("network unreachable")

        with pytest.raises(OSError):
            asyncio.get_event_loop().run_until_complete(M().a_evaluate())

    def test_reraises_keyboard_interrupt_async(self):
        class M(_StubMetric):
            @resilient_evaluation
            async def a_evaluate(self, **kwargs):
                raise KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            asyncio.get_event_loop().run_until_complete(M().a_evaluate())

    def test_non_transient_errors_still_caught(self):
        """ValueError/RuntimeError are not transient — should return inconclusive."""

        class M(_StubMetric):
            @resilient_evaluation
            def evaluate(self, **kwargs):
                raise ValueError("parse error")

        result = M().evaluate()
        assert result.details["inconclusive"] is True


class TestResilientEvaluationLogging:
    def test_logs_warning_on_failure(self, caplog):
        class M(_StubMetric):
            @resilient_evaluation
            async def a_evaluate(self, **kwargs):
                raise ValueError("bad output")

        with caplog.at_level("WARNING"):
            asyncio.get_event_loop().run_until_complete(M(name="bias").a_evaluate())

        assert any("bias" in r.message and "ValueError" in r.message for r in caplog.records)

    def test_does_not_log_exception_message(self, caplog):
        sensitive = "user said: my SSN is 123-45-6789"

        class M(_StubMetric):
            @resilient_evaluation
            async def a_evaluate(self, **kwargs):
                raise ValueError(sensitive)

        with caplog.at_level("WARNING"):
            asyncio.get_event_loop().run_until_complete(M().a_evaluate())

        for record in caplog.records:
            assert sensitive not in record.message
