"""Server-side bounds on test-run execution.

Execution options (concurrency, retries, timeouts) arrive in a test configuration's
attributes, which any caller can set. They are clamped to JobLimitSettings, not refused.
A run also stops itself at EXECUTION_TIME_LIMIT, because the worker's thread pool
ignores Celery's own time limits and a run past the broker's visibility timeout would
be delivered to a second worker.
"""

import asyncio
import logging
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.app.config.settings import JobLimitSettings
from rhesis.backend.jobs.execution.batch.context import (
    DEFAULT_BATCH_CONCURRENCY,
    DEFAULT_INVOKE_MAX_ATTEMPTS,
    DEFAULT_PER_TEST_TIMEOUT,
    DEFAULT_RECOVERY_ROUNDS,
    resolve_execution_options,
)


@pytest.fixture(autouse=True)
def _no_operator_overrides(monkeypatch):
    monkeypatch.delenv("BATCH_CONCURRENCY", raising=False)
    monkeypatch.delenv("RECOVERY_ROUNDS", raising=False)


class TestExecutionOptionsAreClamped:
    def test_oversized_options_are_clamped_to_the_server_maxima(self, caplog):
        limits = JobLimitSettings()
        attrs = {
            "batch_concurrency": 10_000,
            "per_test_timeout": 10**9,
            "invoke_max_attempts": 1_000,
            "invoke_retry_min_wait": 10**6,
            "invoke_retry_max_wait": 10**6,
            "recovery_rounds": 99,
        }

        with caplog.at_level(logging.WARNING):
            options = resolve_execution_options(attrs, "cfg-1")

        assert options["batch_concurrency"] == limits.max_batch_concurrency
        assert options["per_test_timeout"] == limits.max_per_test_timeout
        assert options["invoke_max_attempts"] == limits.max_invoke_attempts
        assert options["invoke_retry_min_wait"] == limits.max_invoke_retry_wait
        assert options["invoke_retry_max_wait"] == limits.max_invoke_retry_wait
        assert options["recovery_rounds"] == limits.max_recovery_rounds
        assert "batch_concurrency=10000 clamped" in caplog.text

    def test_defaults_are_untouched(self):
        options = resolve_execution_options({}, "cfg-1")

        assert options["batch_concurrency"] == DEFAULT_BATCH_CONCURRENCY
        assert options["per_test_timeout"] == DEFAULT_PER_TEST_TIMEOUT
        assert options["invoke_max_attempts"] == DEFAULT_INVOKE_MAX_ATTEMPTS
        assert options["recovery_rounds"] == DEFAULT_RECOVERY_ROUNDS

    def test_defaults_sit_within_the_maxima(self):
        limits = JobLimitSettings()
        assert DEFAULT_BATCH_CONCURRENCY <= limits.max_batch_concurrency
        assert DEFAULT_PER_TEST_TIMEOUT <= limits.max_per_test_timeout
        assert DEFAULT_INVOKE_MAX_ATTEMPTS <= limits.max_invoke_attempts
        assert DEFAULT_RECOVERY_ROUNDS <= limits.max_recovery_rounds
        assert DEFAULT_PER_TEST_TIMEOUT < limits.execution_time_limit

    def test_values_below_the_floor_are_raised(self):
        options = resolve_execution_options(
            {"batch_concurrency": 0, "invoke_max_attempts": -5, "recovery_rounds": -1},
            "cfg-1",
        )

        # A zero-permit semaphore would hang the run forever.
        assert options["batch_concurrency"] == 1
        assert options["invoke_max_attempts"] == 1
        assert options["recovery_rounds"] == 0

    @pytest.mark.parametrize("bad", ["lots", None, float("nan"), float("inf"), [1]])
    def test_unusable_values_fall_back_to_the_default_or_the_ceiling(self, bad):
        options = resolve_execution_options({"batch_concurrency": bad}, "cfg-1")

        assert 1 <= options["batch_concurrency"] <= JobLimitSettings().max_batch_concurrency

    def test_maxima_come_from_settings(self, monkeypatch):
        from rhesis.backend.app.config import settings

        monkeypatch.setenv("MAX_BATCH_CONCURRENCY", "5")
        settings.get_job_limit_settings.cache_clear()
        try:
            options = resolve_execution_options({"batch_concurrency": 20}, "cfg-1")
        finally:
            settings.get_job_limit_settings.cache_clear()

        assert options["batch_concurrency"] == 5


def _ctx(deadline):
    from rhesis.backend.jobs.execution.batch.context import ExecutionContext

    ctx = ExecutionContext(
        test_config=MagicMock(),
        test_run=MagicMock(),
        test_set=MagicMock(),
        endpoint=MagicMock(),
        organization_id="org-1",
        user_id="user-1",
    )
    ctx.deadline = deadline
    return ctx


class TestBatchRunStopsAtItsDeadline:
    def test_tests_still_running_at_the_deadline_fail_with_the_reason(self):
        from rhesis.backend.jobs.execution.batch.runner import RUN_TIME_LIMIT_ERROR, _run_gather

        async def _hangs(*args, **kwargs):
            await asyncio.sleep(60)

        ctx = _ctx(deadline=time.monotonic() + 0.1)
        started = time.monotonic()
        with patch(
            "rhesis.backend.jobs.execution.batch.runner._execute_single_test",
            side_effect=_hangs,
        ):
            results = asyncio.run(_run_gather(ctx, ["t1", "t2"], asyncio.Semaphore(1), None, None))

        assert time.monotonic() - started < 10
        assert ctx.deadline_exceeded is True
        assert [r["status"] for r in results] == ["failed", "failed"]
        assert all(r["error"] == RUN_TIME_LIMIT_ERROR for r in results)

    def test_no_recovery_pass_after_the_deadline(self):
        from rhesis.backend.jobs.execution.batch.runner import (
            RUN_TIME_LIMIT_ERROR,
            _is_retriable_failure,
            run_batch,
        )

        assert not _is_retriable_failure({"status": "failed", "error": RUN_TIME_LIMIT_ERROR})

        ctx = _ctx(deadline=None)
        ctx.recovery_rounds = 3
        ctx.deadline_exceeded = True
        gather = AsyncMock(return_value=[{"test_id": "t1", "status": "failed", "error": "boom"}])
        with patch("rhesis.backend.jobs.execution.batch.runner._run_gather", gather):
            asyncio.run(run_batch(ctx, ["t1"]))

        assert gather.await_count == 1

    def test_batch_sets_the_deadline_from_settings(self):
        from rhesis.backend.jobs.execution.batch import execute_tests_as_batch

        test_run = MagicMock()
        test_run.attributes = {"task_id": "task-1"}
        ctx = _ctx(deadline=None)
        ctx.test_run = test_run
        before = time.monotonic()

        with (
            patch(
                "rhesis.backend.jobs.execution.batch.prefetch_execution_context",
                return_value=ctx,
            ),
            patch("rhesis.backend.jobs.execution.shared.update_test_run_start"),
            patch("rhesis.backend.jobs.execution.batch.run_batch", return_value=MagicMock()),
            patch("rhesis.backend.jobs.execution.batch.run_on_thread_loop", return_value=[]),
        ):
            execute_tests_as_batch(MagicMock(), MagicMock(), test_run, [])

        limit = JobLimitSettings().execution_time_limit
        assert before + limit <= ctx.deadline <= time.monotonic() + limit


class TestSequentialRunStopsAtItsDeadline:
    def test_no_test_starts_after_the_deadline(self):
        from rhesis.backend.jobs.execution.sequential import execute_tests_sequentially

        test_config = MagicMock(user_id=None, organization_id="org-1", attributes={})
        test_run = MagicMock(attributes={"task_id": "task-1"})
        tests = [MagicMock(id="t1"), MagicMock(id="t2")]

        with (
            patch("rhesis.backend.jobs.execution.sequential.update_test_run_start"),
            patch("rhesis.backend.jobs.execution.sequential.resolve_run_models"),
            patch("rhesis.backend.jobs.execution.sequential.get_live_metric_backends"),
            patch(
                "rhesis.backend.jobs.execution.sequential.run_deadline",
                return_value=time.monotonic() - 1,
            ),
            patch("rhesis.backend.jobs.execution.sequential.execute_test") as mock_execute,
            patch("rhesis.backend.jobs.execution.sequential.trigger_results_collection"),
        ):
            execute_tests_sequentially(MagicMock(), test_config, test_run, tests)

        mock_execute.assert_not_called()

    def test_a_test_running_past_the_deadline_is_stopped(self):
        from rhesis.backend.jobs.execution.sequential import execute_tests_sequentially

        async def _hangs(**kwargs):
            await asyncio.sleep(60)

        test_config = MagicMock(user_id=None, organization_id="org-1", attributes={})
        test_run = MagicMock(attributes={"task_id": "task-1"})
        started = time.monotonic()

        with (
            patch("rhesis.backend.jobs.execution.sequential.update_test_run_start"),
            patch("rhesis.backend.jobs.execution.sequential.resolve_run_models"),
            patch("rhesis.backend.jobs.execution.sequential.get_live_metric_backends"),
            patch(
                "rhesis.backend.jobs.execution.sequential.run_deadline",
                return_value=time.monotonic() + 0.2,
            ),
            patch("rhesis.backend.jobs.execution.sequential.execute_test", side_effect=_hangs),
            patch("rhesis.backend.jobs.execution.sequential.trigger_results_collection"),
        ):
            execute_tests_sequentially(MagicMock(), test_config, test_run, [MagicMock(id="t1")])

        assert time.monotonic() - started < 10


class TestCeleryLimitsFollowTheExecutionLimit:
    def test_visibility_timeout_outlasts_the_in_job_limit(self):
        from rhesis.backend.celery.config import CELERY_CONFIG

        visibility = CELERY_CONFIG["broker_transport_options"]["visibility_timeout"]
        assert visibility > JobLimitSettings().execution_time_limit

    def test_exploration_time_limit_is_not_retried(self):
        from rhesis.backend.jobs.base import BaseJob, JobTimeLimitExceeded

        assert JobTimeLimitExceeded in BaseJob.dont_autoretry_for
