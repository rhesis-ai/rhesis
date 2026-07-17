"""HTTP errors must not be scored by metrics and must resolve to Error status."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.app.constants import TestResultStatus
from rhesis.backend.app.services.invokers.common.schemas import ErrorResponse
from rhesis.backend.tasks.execution.batch.evaluation import evaluate_metrics
from rhesis.backend.tasks.execution.executors.metrics import determine_status_from_metrics
from rhesis.backend.tasks.execution.executors.output_providers import TestOutput
from rhesis.backend.tasks.execution.executors.runners import SingleTurnRunner
from rhesis.backend.tasks.execution.response_extractor import is_http_error_response


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
