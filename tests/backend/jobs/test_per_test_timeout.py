"""The per-test limit follows the endpoint's own timeout (up to 2h), and says which limit hit."""

import asyncio
import logging
import selectors
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.app.config.settings import JobLimitSettings
from rhesis.backend.jobs.execution.batch.context import (
    DEFAULT_PER_TEST_TIMEOUT,
    PER_TEST_TIMEOUT_DEFAULT,
    PER_TEST_TIMEOUT_EXPLICIT,
    PER_TEST_TIMEOUT_FROM_ENDPOINT,
    PER_TEST_TIMEOUT_MARGIN,
    effective_endpoint_timeout,
    resolve_execution_options,
    timeout_warnings,
)
from rhesis.backend.jobs.execution.shared import PER_TEST_TIMEOUT_ERROR

RUNNER = "rhesis.backend.jobs.execution.batch.runner"


@pytest.fixture(autouse=True)
def _no_operator_overrides(monkeypatch):
    for var in (
        "BATCH_CONCURRENCY",
        "RECOVERY_ROUNDS",
        "MAX_ENDPOINT_TIMEOUT",
        "MAX_PER_TEST_TIMEOUT",
        "EXECUTION_TIME_LIMIT",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def max_per_test_timeout(monkeypatch):
    """Set MAX_PER_TEST_TIMEOUT for one test."""
    from rhesis.backend.app.config import settings

    def _set(value: int) -> None:
        monkeypatch.setenv("MAX_PER_TEST_TIMEOUT", str(value))
        settings.get_job_limit_settings.cache_clear()

    yield _set
    settings.get_job_limit_settings.cache_clear()


def _endpoint(timeout_seconds=None, connection_type="REST"):
    return MagicMock(timeout_seconds=timeout_seconds, connection_type=connection_type)


class TestDefaultFollowsTheEndpoint:
    def test_no_endpoint_timeout_keeps_the_default(self):
        options = resolve_execution_options({}, "cfg", None)

        assert options["per_test_timeout"] == DEFAULT_PER_TEST_TIMEOUT
        assert options["per_test_timeout_source"] == PER_TEST_TIMEOUT_DEFAULT

    def test_fast_endpoint_keeps_the_default(self):
        options = resolve_execution_options({}, "cfg", 60)

        assert options["per_test_timeout"] == DEFAULT_PER_TEST_TIMEOUT
        assert options["per_test_timeout_source"] == PER_TEST_TIMEOUT_DEFAULT

    def test_slow_endpoint_gets_its_timeout_plus_the_margin(self):
        options = resolve_execution_options({}, "cfg", 3600)

        assert options["per_test_timeout"] == 3600 + PER_TEST_TIMEOUT_MARGIN
        assert options["per_test_timeout_source"] == PER_TEST_TIMEOUT_FROM_ENDPOINT

    def test_a_two_hour_endpoint_fits_under_the_default_maximum(self):
        options = resolve_execution_options({}, "cfg", 7200)

        assert options["per_test_timeout"] == 7200 + PER_TEST_TIMEOUT_MARGIN
        assert options["per_test_timeout"] <= JobLimitSettings().max_per_test_timeout

    def test_the_server_maximum_still_clamps_and_says_so(self, max_per_test_timeout, caplog):
        max_per_test_timeout(3000)

        with caplog.at_level(logging.WARNING):
            options = resolve_execution_options({}, "cfg", 3600)

        assert options["per_test_timeout"] == 3000
        assert "shorter than the endpoint's timeout of 3600s" in caplog.text

    def test_an_explicit_per_test_timeout_wins(self):
        options = resolve_execution_options({"per_test_timeout": 600}, "cfg", 3600)

        assert options["per_test_timeout"] == 600
        assert options["per_test_timeout_source"] == PER_TEST_TIMEOUT_EXPLICIT

    def test_an_unusable_explicit_value_is_not_reported_as_explicit(self):
        options = resolve_execution_options({"per_test_timeout": None}, "cfg", 3600)

        assert options["per_test_timeout"] == 3600 + PER_TEST_TIMEOUT_MARGIN
        assert options["per_test_timeout_source"] == PER_TEST_TIMEOUT_FROM_ENDPOINT

    def test_an_explicit_per_test_timeout_is_still_bounded(self):
        options = resolve_execution_options({"per_test_timeout": 10**9}, "cfg", 3600)

        assert options["per_test_timeout"] == JobLimitSettings().max_per_test_timeout


class TestEffectiveEndpointTimeout:
    def test_the_endpoint_setting_wins(self):
        assert effective_endpoint_timeout(_endpoint(3600, "SDK")) == 3600

    def test_an_sdk_endpoint_without_one_uses_the_sdk_default(self):
        from rhesis.backend.app.services.invokers.sdk_invoker import SDK_FUNCTION_TIMEOUT

        assert effective_endpoint_timeout(_endpoint(None, "SDK")) == SDK_FUNCTION_TIMEOUT

    def test_a_rest_endpoint_without_one_has_none(self):
        assert effective_endpoint_timeout(_endpoint(None, "REST")) is None


def _ctx_for(endpoint, attrs=None, test_ids=("test-1",)):
    """A batch context with execution options resolved the way prefetch resolves them."""
    from rhesis.backend.jobs.execution.batch.context import ExecutionContext

    options = resolve_execution_options(attrs or {}, "cfg", effective_endpoint_timeout(endpoint))
    ctx = ExecutionContext(
        test_config=MagicMock(),
        test_run=MagicMock(),
        test_set=MagicMock(),
        endpoint=endpoint,
        organization_id="org-1",
        user_id="user-1",
        **options,
    )
    ctx.test_data = {
        tid: {"test": MagicMock(), "prompt_content": "", "expected_response": ""}
        for tid in test_ids
    }
    return ctx


class _FastForwardSelector(selectors.DefaultSelector):
    """Skips each idle wait by moving the loop's clock instead of sleeping."""

    def __init__(self):
        super().__init__()
        self.now = 0.0

    def select(self, timeout=None):
        if timeout:
            self.now += timeout
        return super().select(0 if timeout is not None else None)


def _run_on_fast_clock(coro):
    selector = _FastForwardSelector()
    loop = asyncio.SelectorEventLoop(selector)
    loop.time = lambda: selector.now
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _run_single_test(ctx, invocation_seconds):
    from rhesis.backend.jobs.execution.batch.runner import _execute_single_test

    async def _slow_invocation(*args, **kwargs):
        await asyncio.sleep(invocation_seconds)
        return {"output": {"output": "done"}, "penelope_metrics": {}}

    with (
        patch(f"{RUNNER}.is_multi_turn_test", return_value=False),
        patch(f"{RUNNER}.run_test", new=_slow_invocation),
        patch(f"{RUNNER}.evaluate_metrics", new=AsyncMock(return_value={})),
        patch("rhesis.backend.jobs.execution.batch.persist.persist_result"),
    ):
        return await _execute_single_test(ctx, "test-1", asyncio.Semaphore(1))


class TestASlowConnectorInvocationIsNotCutShort:
    THIRTY_FIVE_MINUTES = 35 * 60

    def test_a_35_minute_answer_from_a_3600s_sdk_endpoint_completes(self):
        ctx = _ctx_for(_endpoint(3600, "SDK"))

        result = _run_on_fast_clock(_run_single_test(ctx, self.THIRTY_FIVE_MINUTES))

        assert result["status"] == "succeeded"

    def test_without_the_endpoint_timeout_it_hits_the_per_test_limit(self):
        ctx = _ctx_for(_endpoint(None, "REST"))

        result = _run_on_fast_clock(_run_single_test(ctx, self.THIRTY_FIVE_MINUTES))

        assert result["status"] == "failed"
        assert result["error"].startswith(PER_TEST_TIMEOUT_ERROR)
        assert f"({DEFAULT_PER_TEST_TIMEOUT}s)" in result["error"]
        assert "endpoint's Timeout" in result["error"]

    @pytest.mark.parametrize("exc", [TimeoutError("read timeout"), TimeoutError()])
    def test_a_timeout_raised_inside_the_test_is_not_blamed_on_the_limit(self, exc):
        from rhesis.backend.jobs.execution.batch.runner import (
            _execute_single_test,
            _is_retriable_failure,
        )
        from rhesis.backend.jobs.execution.shared import CALL_TIMEOUT_ERROR

        ctx = _ctx_for(_endpoint(None, "REST"))
        with (
            patch(f"{RUNNER}.is_multi_turn_test", return_value=False),
            patch(f"{RUNNER}.run_test", new=AsyncMock(side_effect=exc)),
        ):
            result = asyncio.run(_execute_single_test(ctx, "test-1", asyncio.Semaphore(1)))

        assert result["status"] == "failed"
        assert result["error"].startswith(CALL_TIMEOUT_ERROR)
        # It already used its retries; a recovery round would only call the slow endpoint again.
        assert _is_retriable_failure(result) is False


class TestTimeoutMessages:
    def test_at_the_server_maximum_it_names_the_setting(self, max_per_test_timeout):
        from rhesis.backend.jobs.execution.batch.context import per_test_timeout_error

        max_per_test_timeout(3000)
        ctx = _ctx_for(_endpoint(3600, "SDK"))

        assert "MAX_PER_TEST_TIMEOUT" in per_test_timeout_error(ctx)

    def test_at_the_default_it_says_how_high_the_timeout_must_go(self):
        from rhesis.backend.jobs.execution.batch.context import per_test_timeout_error

        ctx = _ctx_for(_endpoint(None))

        assert "above 1500s" in per_test_timeout_error(ctx)

    def test_an_explicit_limit_points_at_the_execution_option(self):
        from rhesis.backend.jobs.execution.batch.context import per_test_timeout_error

        ctx = _ctx_for(_endpoint(None), attrs={"per_test_timeout": 60})

        assert "per_test_timeout in the run's execution options" in per_test_timeout_error(ctx)


class TestRunLevelWarnings:
    def test_warns_when_the_worst_case_outlasts_the_run_limit(self):
        limit = JobLimitSettings().execution_time_limit
        ctx = _ctx_for(_endpoint(3600, "SDK"), attrs={"batch_concurrency": 10})

        # 21 tests at 10 at a time is 3 waves of 3900s.
        warnings = timeout_warnings(ctx, 21)

        assert 3 * ctx.per_test_timeout > limit
        assert any("EXECUTION_TIME_LIMIT" in w for w in warnings)

    def test_quiet_when_every_wave_fits(self):
        ctx = _ctx_for(_endpoint(3600, "SDK"), attrs={"batch_concurrency": 10})

        assert timeout_warnings(ctx, 10) == []

    def test_quiet_for_a_re_score(self):
        ctx = _ctx_for(_endpoint(3600, "SDK"), attrs={"batch_concurrency": 10})
        ctx.stored_outputs = {}

        assert timeout_warnings(ctx, 50) == []

    def test_quiet_at_the_default_limit(self):
        # 50 tests at the 1800s default is a worst case ordinary runs never come near.
        ctx = _ctx_for(_endpoint(None), attrs={"batch_concurrency": 10})

        assert timeout_warnings(ctx, 50) == []

    def test_warns_when_the_clamp_cuts_the_endpoint_timeout(self, max_per_test_timeout):
        max_per_test_timeout(3000)
        ctx = _ctx_for(_endpoint(3600, "SDK"))

        warnings = timeout_warnings(ctx, 1)

        assert any("shorter than the endpoint's Timeout of 3600s" in w for w in warnings)

    def test_the_warning_is_recorded_on_the_run_and_in_the_activity_log(self):
        from rhesis.backend.jobs.execution.batch import _record_timeout_warnings

        ctx = _ctx_for(_endpoint(3600, "SDK"), test_ids=[f"t{i}" for i in range(21)])
        ctx.test_run.attributes = {"task_id": "task-1"}
        ctx.test_run.user_id = "run-owner"
        emitted = []

        with patch("rhesis.backend.app.crud.test_run.update_test_run") as update:
            _record_timeout_warnings(MagicMock(), ctx, 21, emitted.append)

        stored = update.call_args.args[2].attributes
        assert stored["task_id"] == "task-1"
        assert any("EXECUTION_TIME_LIMIT" in w for w in stored["warnings"])
        assert any(m.startswith("Warning:") for m in emitted)
        # The run's owner, not the test configuration's (ctx.user_id).
        assert update.call_args.kwargs["user_id"] == "run-owner"

    def test_a_redelivered_run_records_each_warning_once(self):
        from rhesis.backend.jobs.execution.batch import _record_timeout_warnings

        ctx = _ctx_for(_endpoint(3600, "SDK"), test_ids=[f"t{i}" for i in range(21)])
        ctx.test_run.attributes = {}

        with patch("rhesis.backend.app.crud.test_run.update_test_run") as update:
            _record_timeout_warnings(MagicMock(), ctx, 21)
            _record_timeout_warnings(MagicMock(), ctx, 21)

        warnings = update.call_args.args[2].attributes["warnings"]
        assert len(warnings) == len(set(warnings)) == 1


class TestOneTimeoutCeiling:
    """MAX_ENDPOINT_TIMEOUT is the one ceiling; the per-test and run limits follow it."""

    def test_defaults_derive_from_the_endpoint_ceiling(self):
        limits = JobLimitSettings()

        assert limits.max_endpoint_timeout == 7200
        assert limits.max_per_test_timeout == 7200 + PER_TEST_TIMEOUT_MARGIN
        assert limits.execution_time_limit > limits.max_per_test_timeout

    def test_raising_the_endpoint_ceiling_raises_the_others(self, monkeypatch):
        monkeypatch.setenv("MAX_ENDPOINT_TIMEOUT", "10800")
        limits = JobLimitSettings()

        assert limits.max_per_test_timeout == 10800 + PER_TEST_TIMEOUT_MARGIN
        assert limits.execution_time_limit > limits.max_per_test_timeout

    def test_a_low_endpoint_ceiling_keeps_the_old_floors(self, monkeypatch):
        monkeypatch.setenv("MAX_ENDPOINT_TIMEOUT", "60")
        limits = JobLimitSettings()

        assert limits.max_per_test_timeout == DEFAULT_PER_TEST_TIMEOUT
        assert limits.execution_time_limit == 6600

    def test_explicit_values_still_win(self, monkeypatch):
        monkeypatch.setenv("MAX_PER_TEST_TIMEOUT", "3600")
        monkeypatch.setenv("EXECUTION_TIME_LIMIT", "6600")
        limits = JobLimitSettings()

        assert (limits.max_per_test_timeout, limits.execution_time_limit) == (3600, 6600)

    def test_explicit_values_that_disagree_are_logged(self, monkeypatch, caplog):
        monkeypatch.setenv("MAX_PER_TEST_TIMEOUT", "3600")
        with caplog.at_level(logging.WARNING):
            JobLimitSettings()

        assert "below MAX_ENDPOINT_TIMEOUT" in caplog.text


class TestEndpointTimeoutFollowsTheCeiling:
    @pytest.fixture
    def endpoint_ceiling(self, monkeypatch):
        from rhesis.backend.app.config import settings

        def _set(value: int) -> None:
            monkeypatch.setenv("MAX_ENDPOINT_TIMEOUT", str(value))
            settings.get_job_limit_settings.cache_clear()

        yield _set
        settings.get_job_limit_settings.cache_clear()

    def test_writes_are_bounded_by_the_ceiling(self, endpoint_ceiling):
        from pydantic import ValidationError

        from rhesis.backend.app.schemas.endpoint import EndpointCreate

        endpoint_ceiling(600)
        with pytest.raises(ValidationError, match="between 1 and 600"):
            EndpointCreate(name="ep", connection_type="REST", timeout_seconds=601)

    def test_stored_metadata_sent_back_is_capped_not_refused(self, endpoint_ceiling):
        from rhesis.backend.app.schemas.endpoint import EndpointUpdate

        endpoint_ceiling(600)
        update = EndpointUpdate(endpoint_metadata={"timeout_seconds": 3600})

        assert update.endpoint_metadata.timeout_seconds == 600

    def test_the_response_shows_the_capped_value(self, endpoint_ceiling):
        from rhesis.backend.app.schemas.endpoint import Endpoint as EndpointSchema

        endpoint_ceiling(600)
        data = EndpointSchema._extract_timeout_from_metadata(
            {"endpoint_metadata": {"timeout_seconds": 3600}}
        )

        assert data["timeout_seconds"] == 600

    def test_an_endpoint_saved_above_a_lowered_ceiling_still_loads(self, endpoint_ceiling):
        from rhesis.backend.app.schemas.endpoint import EndpointMetadata

        endpoint_ceiling(600)

        assert EndpointMetadata(timeout_seconds=3600).timeout_seconds == 3600

    def test_it_is_capped_when_used(self, endpoint_ceiling):
        from rhesis.backend.app.models.endpoint import Endpoint

        endpoint_ceiling(600)
        endpoint = Endpoint(endpoint_metadata={"timeout_seconds": 3600})

        assert endpoint.timeout_seconds == 600
