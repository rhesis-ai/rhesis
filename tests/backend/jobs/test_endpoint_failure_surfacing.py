"""A failed target call must reach the user with its status code and the target's reason.

Regression cover for a customer report: a test set whose endpoint answered 400 ("blocked by
safeguarding") showed status Error with "No response available" and nothing else anywhere in
the UI. Three separate defects produced that, and each gets a test here:

1. Batch single-turn raised the invoker's ``ErrorResponse`` as an exception, so only
   ``str(exc)`` survived and it was stored under ``error`` -- a key the detail view does not
   read -- with no ``status_code`` or ``error_type``.
2. ``extract_response_with_fallback`` preferred the short ``message`` over ``output``,
   dropping the target's response body (the part naming the actual reason).
3. Failures with no HTTP status (SDK/connector, WebSocket mid-stream) were not detected as
   failures at all, so their error text was scored into a Pass/Fail verdict.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.app.outcomes import Execution, classify_metrics
from rhesis.backend.app.services.endpoint.result_processing import process_endpoint_result
from rhesis.backend.app.services.invokers.common.errors import (
    INTERNAL_ERROR_TYPE,
    EndpointInvocationError,
    classify_error_response,
)
from rhesis.backend.app.services.invokers.common.schemas import ErrorResponse
from rhesis.backend.app.utils.response_extractor import (
    NARRATION_MESSAGE_LIMIT,
    as_response_dict,
    has_endpoint_failure_in_result,
    is_endpoint_failure,
    summarize_endpoint_failure,
)
from rhesis.backend.jobs.execution.batch.runner import (
    _failure_result,
    _is_retriable_failure,
)

SAFEGUARDING_BODY = '{"detail":"Blocked by safeguarding policy"}'


def _http_400_error_response() -> ErrorResponse:
    """Exactly what RestEndpointInvoker._handle_http_error builds for a 400."""
    return ErrorResponse(
        output=(
            f"HTTP 400 error from endpoint: Bad Request. Response content: {SAFEGUARDING_BODY}"
        ),
        error=True,
        error_type="http_error",
        message="HTTP 400 error from endpoint",
        status_code=400,
        reason="Bad Request",
        response_content=SAFEGUARDING_BODY,
    )


@pytest.mark.unit
class TestStoredOutputKeepsTheReason:
    """What lands in ``test_output`` has to answer "why did this fail?"."""

    def test_output_keeps_the_targets_response_body(self):
        """The reason lives in the response body, so ``output`` must not be the short
        ``message`` variant -- that stops at "HTTP 400 error from endpoint".
        """
        processed = process_endpoint_result(_http_400_error_response())

        assert SAFEGUARDING_BODY in processed["output"]
        assert processed["output"] != "HTTP 400 error from endpoint"

    def test_structured_fields_survive_alongside_the_message(self):
        processed = process_endpoint_result(_http_400_error_response())

        assert processed["status_code"] == 400
        assert processed["error_type"] == "http_error"
        assert processed["reason"] == "Bad Request"
        assert processed["response_content"] == SAFEGUARDING_BODY

    def test_unknown_error_still_reports_something(self):
        """An error carrying neither text field must not render as an empty response."""
        processed = process_endpoint_result({"error": True, "error_type": "http_error"})

        assert processed["output"] == "Unknown error occurred"


@pytest.mark.unit
class TestFailuresWithoutAnHttpStatus:
    """SDK/connector and network failures never carry a status code. They are still
    failures, and scoring their error text into a verdict is the worst outcome available.
    """

    @pytest.mark.parametrize(
        "error_type",
        ["sdk_function_error", "sdk_timeout", "sdk_disconnected", "network_error"],
    )
    def test_detected_as_a_failure(self, error_type):
        response = ErrorResponse(
            output=f"failure: {error_type}",
            error=True,
            error_type=error_type,
            message=error_type,
        )
        processed = process_endpoint_result(response)

        assert is_endpoint_failure(processed) is True
        assert has_endpoint_failure_in_result(processed) is True

    def test_failure_forces_error_never_a_verdict(self):
        """The whole point: an unscoreable call must not become Pass."""
        execution, verdict = classify_metrics(
            {"Accuracy": {"is_successful": True}}, endpoint_error=True
        )

        assert execution == Execution.ERROR
        assert verdict is None

    def test_a_target_mapping_an_error_field_is_not_a_failure(self):
        """``error_type`` is required alongside ``error`` so a target whose own mapped
        response happens to contain an ``error`` field is not mistaken for a failure.
        """
        assert is_endpoint_failure({"output": "answer", "error": "some mapped field"}) is False

    def test_success_is_untouched(self):
        assert is_endpoint_failure({"output": "the model answered", "error": False}) is False


@pytest.mark.unit
class TestBatchRoutesPermanentFailuresAsResults:
    """The batch path's structural fix: a permanent rejection is a result, not a crash."""

    @staticmethod
    async def _run_single_turn_with(invoke_result):
        from rhesis.backend.jobs.execution.batch.invocation import _run_single_turn

        ctx = MagicMock()
        ctx.endpoint.id = "endpoint-1"
        ctx.test_run.attributes = {}
        ctx.organization_id = "org-1"
        ctx.user_id = "user-1"
        ctx.invoke_max_attempts = 1
        ctx.invoke_retry_min_wait = 0
        ctx.invoke_retry_max_wait = 0
        ctx.input_files = {}

        service = MagicMock()
        service.invoke_endpoint = AsyncMock(return_value=invoke_result)

        with (
            patch(
                "rhesis.backend.app.dependencies.get_endpoint_service",
                return_value=service,
            ),
            patch(
                "rhesis.backend.jobs.execution.batch.invocation.load_input_files_lazy",
                new=AsyncMock(return_value=None),
            ),
        ):
            return await _run_single_turn(ctx, "test-1", "a prompt", {}, [])

    @pytest.mark.asyncio
    async def test_400_is_returned_as_output_not_raised(self):
        """Previously this raised, and the error reached the DB as ``{"error": str(exc)}``
        with no ``output`` key -- which is what rendered as "No response available".
        """
        result = await self._run_single_turn_with(_http_400_error_response())

        output = result["output"]
        assert output["status_code"] == 400
        assert output["error_type"] == "http_error"
        assert SAFEGUARDING_BODY in output["output"]

    @pytest.mark.asyncio
    async def test_returned_output_is_recognised_as_a_failure(self):
        """So create_test_result_record classifies it Error by the endpoint-failure rule
        rather than falling through to the "no metrics" rule, and a later re-score of the
        row does not try to grade the error text.
        """
        result = await self._run_single_turn_with(_http_400_error_response())

        assert has_endpoint_failure_in_result(result["output"]) is True

    @pytest.mark.asyncio
    async def test_transient_failure_still_propagates(self):
        """Recovery rounds are a flaky endpoint's remaining chance; reporting a transient
        failure as a result here would silently retire that retry.
        """
        transient = ErrorResponse(
            output="HTTP 503 error from endpoint: Service Unavailable",
            error=True,
            error_type="http_error",
            message="HTTP 503 error from endpoint",
            status_code=503,
        )

        with pytest.raises(EndpointInvocationError):
            await self._run_single_turn_with(transient)


@pytest.mark.unit
class TestPermanentFailuresAreNotReInvoked:
    """A 400 fails identically on a retry; re-invoking only spends another target call."""

    def test_permanent_invoker_failure_is_not_retried(self):
        exc = classify_error_response(_http_400_error_response())
        result = _failure_result("test-1", exc, 12.0)

        assert result["transient"] is False
        assert result["status_code"] == 400
        assert _is_retriable_failure(result) is False

    def test_transient_invoker_failure_is_still_retried(self):
        exc = EndpointInvocationError("boom", transient=True, status_code=503)
        result = _failure_result("test-1", exc, 12.0)

        assert _is_retriable_failure(result) is True

    def test_our_own_unexpected_exception_still_gets_a_recovery_round(self):
        """EndpointService tags its own bugs error_type="internal_error", transient=False.
        Those are the "unexpected exceptions" recovery rounds exist for, so a blanket
        "non-transient means don't retry" would quietly remove their only second chance.
        """
        exc = EndpointInvocationError(
            "some sqlalchemy explosion",
            transient=False,
            status_code=500,
            error_type=INTERNAL_ERROR_TYPE,
        )
        result = _failure_result("test-1", exc, 12.0)

        assert _is_retriable_failure(result) is True

    def test_unclassified_failure_keeps_the_previous_behaviour(self):
        """No ``transient`` key means no invoker verdict, so fall back to string sniffing."""
        assert _is_retriable_failure({"status": "failed", "error": "something odd"}) is True
        assert _is_retriable_failure({"status": "failed", "error": "Timeout after 30s"}) is False


@pytest.mark.unit
class TestOurOwnFailuresAreNotBlamedOnTheTarget:
    """`internal_error` means we broke, not the endpoint. Attributing it would send a
    customer debugging a service that never received the request.
    """

    def test_persisted_error_record_omits_internal_error_attribution(self):
        from rhesis.backend.jobs.execution.batch import _persist_failed_results

        captured: dict = {}

        def _fake_persist(_ctx, _tid, _test, output, *args):
            captured.update(output)

        ctx = MagicMock()
        ctx.organization_id = "org-1"
        ctx.user_id = "user-1"
        ctx.project_id = None
        ctx.test_run.id = "11111111-1111-1111-1111-111111111111"
        ctx.test_data_snapshot = {"22222222-2222-2222-2222-222222222222": {"test": MagicMock()}}

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        with (
            patch("rhesis.backend.app.database.get_db_with_tenant_variables") as get_db,
            patch(
                "rhesis.backend.jobs.execution.batch.persist.persist_result",
                new=_fake_persist,
            ),
        ):
            get_db.return_value.__enter__.return_value = db
            _persist_failed_results(
                ctx,
                [
                    {
                        "test_id": "22222222-2222-2222-2222-222222222222",
                        "status": "failed",
                        "error": "internal boom",
                        "error_type": INTERNAL_ERROR_TYPE,
                        "status_code": 500,
                        "execution_time": 5,
                    }
                ],
            )

        # The message is kept so the row still explains itself...
        assert captured["output"] == "internal boom"
        # ...but nothing marks it as the target's failure, so the UI won't claim the
        # endpoint returned HTTP 500.
        assert "status_code" not in captured
        assert "error_type" not in captured
        assert is_endpoint_failure(captured) is False

    def test_a_real_target_rejection_is_still_attributed(self):
        from rhesis.backend.jobs.execution.batch import _persist_failed_results

        captured: dict = {}

        def _fake_persist(_ctx, _tid, _test, output, *args):
            captured.update(output)

        ctx = MagicMock()
        ctx.organization_id = "org-1"
        ctx.user_id = "user-1"
        ctx.project_id = None
        ctx.test_run.id = "11111111-1111-1111-1111-111111111111"
        ctx.test_data_snapshot = {"22222222-2222-2222-2222-222222222222": {"test": MagicMock()}}

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        with (
            patch("rhesis.backend.app.database.get_db_with_tenant_variables") as get_db,
            patch(
                "rhesis.backend.jobs.execution.batch.persist.persist_result",
                new=_fake_persist,
            ),
        ):
            get_db.return_value.__enter__.return_value = db
            _persist_failed_results(
                ctx,
                [
                    {
                        "test_id": "22222222-2222-2222-2222-222222222222",
                        "status": "failed",
                        "error": "HTTP 400 error from endpoint",
                        "error_type": "http_error",
                        "status_code": 400,
                        "execution_time": 5,
                    }
                ],
            )

        assert captured["status_code"] == 400
        assert is_endpoint_failure(captured) is True


@pytest.mark.unit
class TestInPlaceExecutionErrorMapping:
    """`POST /tests/execute` must report a target rejection without laundering our own
    bugs' exception text into the response.
    """

    def test_target_rejection_reports_the_targets_status_and_detail(self):
        from rhesis.backend.app.error_handlers import UpstreamHTTPException
        from rhesis.backend.app.utils.execution_validation import handle_execution_error

        exc = classify_error_response(_http_400_error_response())
        result = handle_execution_error(exc, operation="execute test")

        assert isinstance(result, UpstreamHTTPException)
        assert result.status_code == 400
        assert SAFEGUARDING_BODY in str(result.detail)

    def test_our_own_failure_is_not_attributed_to_the_endpoint(self):
        from rhesis.backend.app.error_handlers import UpstreamHTTPException
        from rhesis.backend.app.utils.execution_validation import handle_execution_error

        exc = EndpointInvocationError(
            "/srv/rhesis/secret/path exploded",
            transient=False,
            status_code=500,
            error_type=INTERNAL_ERROR_TYPE,
        )
        result = handle_execution_error(exc, operation="execute test")

        # Not an upstream failure, and the internal text must not reach the caller.
        assert not isinstance(result, UpstreamHTTPException)
        assert result.status_code == 500
        assert "secret/path" not in str(result.detail)


@pytest.mark.unit
class TestActivityLogNarration:
    """The Jobs page is where someone goes to ask why a run produced nothing."""

    def test_summary_names_the_status_and_the_reason(self):
        summary = summarize_endpoint_failure(process_endpoint_result(_http_400_error_response()))

        assert summary is not None
        assert summary["status_code"] == 400
        assert "400" in summary["summary"]
        assert SAFEGUARDING_BODY in summary["message"]

    def test_status_is_not_repeated_when_the_text_already_names_it(self):
        summary = summarize_endpoint_failure(process_endpoint_result(_http_400_error_response()))

        assert summary is not None
        assert summary["summary"].count("400") == 1

    def test_failure_without_a_status_code_still_reads_sensibly(self):
        response = ErrorResponse(
            output="SDK function error: rejected by policy",
            error=True,
            error_type="sdk_function_error",
            message="rejected by policy",
        )
        summary = summarize_endpoint_failure(process_endpoint_result(response))

        assert summary is not None
        assert summary["status_code"] is None
        assert "rejected by policy" in summary["summary"]

    def test_returns_none_for_a_successful_result(self):
        assert summarize_endpoint_failure({"output": "the model answered"}) is None

    def test_a_huge_response_body_is_capped(self):
        """A target may answer a 4xx with an HTML error page or an echoed payload. Each
        narrated test becomes an ActivityLog row on an unbounded Text column, so the
        summary has to be bounded even though the stored test_output stays complete.
        """
        huge = ErrorResponse(
            output=f"HTTP 400 error from endpoint: Bad Request. Response content: {'x' * 50_000}",
            error=True,
            error_type="http_error",
            message="HTTP 400 error from endpoint",
            status_code=400,
            response_content="x" * 50_000,
        )
        processed = process_endpoint_result(huge)
        summary = summarize_endpoint_failure(processed)

        assert summary is not None
        assert len(summary["message"]) <= NARRATION_MESSAGE_LIMIT + len("... (truncated)")
        assert summary["message"].endswith("... (truncated)")
        # The status code still leads the line, so the narration stays useful.
        assert "400" in summary["summary"]
        # ...and the untruncated body remains available for the detail view.
        assert len(processed["response_content"]) == 50_000

    def test_a_normal_reason_is_not_truncated(self):
        """The case that prompted all this is ~100 characters; it must survive whole."""
        summary = summarize_endpoint_failure(process_endpoint_result(_http_400_error_response()))

        assert summary is not None
        assert SAFEGUARDING_BODY in summary["message"]
        assert "truncated" not in summary["message"]


@pytest.mark.unit
class TestResultNormalisation:
    """`_run_single_turn` converts the raised ErrorResponse with the shared normalizer
    rather than a local to_dict()/dict() pair, which missed the Pydantic v1/v2 variants
    and could raise on anything unexpected.
    """

    def test_error_response_is_normalised(self):
        assert as_response_dict(_http_400_error_response())["status_code"] == 400

    def test_a_dict_passes_through_by_reference(self):
        # _run_single_turn pops the deferred trace off the result, so the caller has to be
        # handed the same object rather than a copy.
        original = {"output": "answer"}
        assert as_response_dict(original) is original

    def test_an_unconvertible_object_does_not_raise(self):
        class Opaque:
            pass

        assert as_response_dict(Opaque()) == {}
