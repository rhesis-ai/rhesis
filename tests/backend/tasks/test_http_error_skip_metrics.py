"""HTTP errors must not be scored by metrics and must resolve to Error status."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.app.constants import TestResultStatus
from rhesis.backend.app.services.invokers.common.errors import EndpointInvocationError
from rhesis.backend.app.services.invokers.common.schemas import ErrorResponse
from rhesis.backend.tasks.execution.batch.evaluation import evaluate_metrics
from rhesis.backend.tasks.execution.executors.metrics import determine_status_from_metrics
from rhesis.backend.tasks.execution.executors.output_providers import TestOutput
from rhesis.backend.tasks.execution.executors.runners import MultiTurnRunner, SingleTurnRunner
from rhesis.backend.tasks.execution.penelope_target import BackendEndpointTarget
from rhesis.backend.tasks.execution.response_extractor import (
    has_http_error_in_result,
    is_http_error_response,
)


def _multi_turn_trace_with_first_http_error(status_code: int = 503) -> dict:
    """Penelope-style trace where the first target message hit an HTTP error."""
    error_details = {
        "error": True,
        "error_type": "http_error",
        "status_code": status_code,
        "message": "Service Unavailable",
        "output": "Service Unavailable",
    }
    tool_content = json.dumps(
        {
            "success": False,
            "output": {},
            "error": "Service Unavailable",
            "metadata": {"error_details": error_details},
        }
    )
    return {
        "history": [
            {
                "turn_number": 1,
                "target_interaction": {
                    "tool_name": "send_message_to_target",
                    "tool_message": {"content": tool_content},
                },
            }
        ],
        "conversation_summary": [],
        "metrics": {"Goal Achievement": {"is_successful": False}},
    }


class TestIsHttpErrorResponse:
    def test_error_type_http_error(self):
        assert is_http_error_response(
            {
                "error": True,
                "error_type": "http_error",
                "status_code": 405,
                "message": "Method Not Allowed",
                "output": "Method Not Allowed",
            }
        )

    def test_error_flag_with_status_ge_400(self):
        assert is_http_error_response(
            {
                "error": True,
                "status_code": 503,
                "message": "Service Unavailable",
                "output": "Service Unavailable",
            }
        )

    def test_error_response_object(self):
        resp = ErrorResponse(
            output="Not Found",
            error_type="http_error",
            message="404 Not Found",
            status_code=404,
        )
        assert is_http_error_response(resp)

    def test_success_response(self):
        assert not is_http_error_response({"output": "hello", "error": False})

    def test_network_error_without_http_status(self):
        assert not is_http_error_response(
            {
                "error": True,
                "error_type": "network_error",
                "message": "Connection refused",
                "output": "Connection refused",
            }
        )

    def test_empty_result(self):
        assert not is_http_error_response(None)
        assert not is_http_error_response({})


class TestHasHttpErrorInResult:
    def test_flat_http_error(self):
        assert has_http_error_in_result(
            {
                "error": True,
                "error_type": "http_error",
                "status_code": 405,
                "message": "Method Not Allowed",
                "output": "Method Not Allowed",
            }
        )

    def test_multi_turn_first_message_http_error(self):
        assert has_http_error_in_result(_multi_turn_trace_with_first_http_error(503))

    def test_multi_turn_successful_first_message(self):
        tool_content = json.dumps(
            {
                "success": True,
                "output": {"response": "hello"},
                "error": None,
                "metadata": {},
            }
        )
        trace = {
            "history": [
                {
                    "turn_number": 1,
                    "target_interaction": {
                        "tool_name": "send_message_to_target",
                        "tool_message": {"content": tool_content},
                    },
                }
            ]
        }
        assert not has_http_error_in_result(trace)

    def test_multi_turn_later_turn_http_error_ignored(self):
        ok = json.dumps(
            {
                "success": True,
                "output": {"response": "hello"},
                "error": None,
                "metadata": {},
            }
        )
        http_err = json.dumps(
            {
                "success": False,
                "output": {},
                "error": "503",
                "metadata": {
                    "error_details": {
                        "error": True,
                        "error_type": "http_error",
                        "status_code": 503,
                        "message": "Service Unavailable",
                        "output": "Service Unavailable",
                    }
                },
            }
        )
        trace = {
            "history": [
                {
                    "turn_number": 1,
                    "target_interaction": {
                        "tool_name": "send_message_to_target",
                        "tool_message": {"content": ok},
                    },
                },
                {
                    "turn_number": 2,
                    "target_interaction": {
                        "tool_name": "send_message_to_target",
                        "tool_message": {"content": http_err},
                    },
                },
            ]
        }
        assert not has_http_error_in_result(trace)


class TestSingleTurnRunnerSkipsHttpErrorMetrics:
    @pytest.mark.asyncio
    async def test_skips_metrics_on_http_error(self):
        http_error = {
            "error": True,
            "error_type": "http_error",
            "status_code": 405,
            "message": "Method Not Allowed",
            "output": "Method Not Allowed",
        }
        mock_provider = MagicMock()
        mock_provider.get_output = AsyncMock(
            return_value=TestOutput(
                response=http_error,
                execution_time=12.5,
                source="live",
            )
        )

        mock_test = MagicMock()
        mock_test.id = "test-1"
        mock_metric = MagicMock()
        mock_metric.class_name = "SomeMetric"

        evaluate_mock = MagicMock()
        with (
            patch(
                "rhesis.backend.tasks.execution.executors.runners.get_test_metrics",
                return_value=[mock_metric],
            ),
            patch(
                "rhesis.backend.tasks.execution.executors.runners.prepare_metric_configs",
                return_value=[mock_metric],
            ),
            patch(
                "rhesis.backend.tasks.execution.executors.runners.evaluate_single_turn_metrics",
                evaluate_mock,
            ),
        ):
            runner = SingleTurnRunner()
            exec_time, result, metrics = await runner.run(
                db=MagicMock(),
                test=mock_test,
                endpoint_id="ep-1",
                organization_id="org-1",
                user_id="user-1",
                prompt_content="hello",
                expected_response="",
                evaluate_metrics=True,
                output_provider=mock_provider,
            )

        evaluate_mock.assert_not_called()
        assert exec_time == 12.5
        assert result == http_error
        assert metrics == {}
        assert determine_status_from_metrics(metrics) == TestResultStatus.ERROR.value


class TestMultiTurnRunnerSkipsHttpErrorMetrics:
    @pytest.mark.asyncio
    async def test_skips_metrics_when_first_message_is_http_error(self):
        trace = _multi_turn_trace_with_first_http_error(503)
        mock_provider = MagicMock()
        mock_provider.get_output = AsyncMock(
            return_value=TestOutput(
                response=trace,
                execution_time=42.0,
                source="live",
                metrics={"Goal Achievement": {"is_successful": False}},
            )
        )

        evaluate_mock = MagicMock(return_value={"Extra": {"is_successful": False}})
        with (
            patch(
                "rhesis.backend.tasks.execution.executors.runners._get_endpoint_routing",
                return_value=(None, None),
            ),
            patch(
                "rhesis.backend.tasks.execution.executors.runners.evaluate_multi_turn_metrics",
                evaluate_mock,
            ),
        ):
            runner = MultiTurnRunner()
            exec_time, result, metrics = await runner.run(
                db=MagicMock(),
                test=MagicMock(id="test-1"),
                endpoint_id="ep-1",
                organization_id="org-1",
                user_id="user-1",
                output_provider=mock_provider,
            )

        evaluate_mock.assert_not_called()
        assert exec_time == 42.0
        assert result == trace
        assert metrics == {}
        assert determine_status_from_metrics(metrics) == TestResultStatus.ERROR.value


class TestBatchEvaluateMetricsSkipsHttpError:
    @pytest.mark.asyncio
    async def test_returns_empty_on_http_error(self):
        ctx = MagicMock()
        ctx.metric_configs = [MagicMock()]
        evaluator = MagicMock()
        evaluator.a_evaluate = AsyncMock(return_value={"metric": {"is_successful": False}})

        result = await evaluate_metrics(
            ctx=ctx,
            evaluator=evaluator,
            test=MagicMock(),
            test_id="test-1",
            output={
                "error": True,
                "error_type": "http_error",
                "status_code": 503,
                "message": "Service Unavailable",
                "output": "Service Unavailable",
            },
            prompt_content="hello",
            expected_response="",
            is_multi_turn=False,
            penelope_metrics={"goal": {"is_successful": True}},
        )

        evaluator.a_evaluate.assert_not_called()
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_empty_on_multi_turn_first_message_http_error(self):
        ctx = MagicMock()
        ctx.metric_configs = [MagicMock()]
        evaluator = MagicMock()
        evaluator.a_evaluate = AsyncMock(return_value={"metric": {"is_successful": False}})

        result = await evaluate_metrics(
            ctx=ctx,
            evaluator=evaluator,
            test=MagicMock(),
            test_id="test-1",
            output=_multi_turn_trace_with_first_http_error(405),
            prompt_content="",
            expected_response="",
            is_multi_turn=True,
            penelope_metrics={"Goal Achievement": {"is_successful": False}},
        )

        evaluator.a_evaluate.assert_not_called()
        assert result == {}


class TestBackendEndpointTargetPreservesHttpError:
    @pytest.mark.asyncio
    async def test_async_preserves_endpoint_invocation_error_details(self):
        target = BackendEndpointTarget.__new__(BackendEndpointTarget)
        target.endpoint_id = "ep-1"
        target.organization_id = "org-1"
        target.user_id = "user-1"
        target.project_id = None
        target.test_execution_context = {"test_id": "test-1"}
        target.params = None
        target._endpoint = MagicMock()
        target._current_trace_id = None
        target._deferred_traces = []
        target._invoke_max_attempts = 1
        target._invoke_retry_min_wait = 0.01
        target._invoke_retry_max_wait = 0.01
        target.endpoint_service = MagicMock()

        error = EndpointInvocationError(
            "Method Not Allowed",
            transient=False,
            status_code=405,
            error_type="http_error",
        )

        with patch(
            "rhesis.backend.tasks.execution.batch.retry.invoke_with_retry",
            AsyncMock(side_effect=error),
        ):
            response = await target.a_send_message("hello")

        assert response.success is False
        assert response.metadata["error_details"]["error_type"] == "http_error"
        assert response.metadata["error_details"]["status_code"] == 405
        assert is_http_error_response(response.metadata["error_details"])
