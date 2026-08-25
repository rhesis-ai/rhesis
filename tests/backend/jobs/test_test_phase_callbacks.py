"""The on_test_phase callback chain that drives the verdict grid's live columns.

Every test that enters the batch must eventually report "done", or the
grid's completed count never reaches total and the progress readout stalls
short of 100% forever.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.jobs.execution.batch.runner import run_batch


def _ctx(test_ids, *, recovery_rounds=0):
    ctx = MagicMock()
    ctx.batch_concurrency = 4
    ctx.per_test_timeout = 60
    ctx.recovery_rounds = recovery_rounds
    ctx.celery_task_id = None
    ctx.existing_result_ids = set()
    ctx.test_data = {tid: {"test": MagicMock(category=None)} for tid in test_ids}
    ctx.input_files = {}
    return ctx


@pytest.mark.unit
class TestPhaseReporting:
    def test_skipped_test_still_reports_done(self):
        """An idempotency skip returns before any phase fires, so without an
        explicit report the test would sit in-flight forever.
        """
        ctx = _ctx(["t1"])
        ctx.existing_result_ids = {"t1"}
        phases = []

        asyncio.run(run_batch(ctx, ["t1"], on_test_phase=lambda tid, p: phases.append((tid, p))))

        assert phases == [("t1", "done")]

    def test_missing_prefetch_data_still_reports_done(self):
        ctx = _ctx([])
        ctx.test_data = {}
        phases = []

        asyncio.run(run_batch(ctx, ["t1"], on_test_phase=lambda tid, p: phases.append((tid, p))))

        assert phases == [("t1", "done")]

    def test_recovery_pass_keeps_reporting_phases(self):
        """Without on_test_phase threaded into the recovery round the live
        grid freezes on the main pass's last state for the whole retry.
        """
        ctx = _ctx(["t1"], recovery_rounds=1)
        phases = []
        attempts = {"n": 0}

        async def _fake_single(ctx, test_id, semaphore, agent, evaluator, **kwargs):
            attempts["n"] += 1
            cb = kwargs.get("on_test_phase")
            if cb:
                cb(test_id, "generating")
                cb(test_id, "done")
            # Fail the first attempt so a recovery round is triggered.
            if attempts["n"] == 1:
                return {"test_id": test_id, "status": "failed", "error": "boom"}
            return {"test_id": test_id, "status": "succeeded", "execution_time": 1}

        with patch(
            "rhesis.backend.jobs.execution.batch.runner._execute_single_test",
            side_effect=_fake_single,
        ):
            asyncio.run(
                run_batch(
                    ctx,
                    ["t1"],
                    on_test_phase=lambda tid, p: phases.append((tid, p)),
                )
            )

        assert attempts["n"] == 2, "recovery round did not run"
        # Two full cycles: one per attempt.
        assert phases == [
            ("t1", "generating"),
            ("t1", "done"),
            ("t1", "generating"),
            ("t1", "done"),
        ]


@pytest.mark.unit
class TestFailureNarrationIsNotThrottled:
    def test_every_failure_emits_its_error(self):
        """The throttle keeps activity-log volume down, but a failure line
        carries the error text -- the reason to read the log at all.

        Concurrency is pinned to 1 so completion order is submission order
        and ``current`` is the test's index: the failures below sit at odd
        positions, which ``current % emit_interval`` (interval 2) skips. With
        a nondeterministic order they would land on an emitting slot roughly
        half the time and the test would pass without the fix.
        """
        test_ids = [f"t{i}" for i in range(40)]
        ctx = _ctx(test_ids)
        ctx.batch_concurrency = 1
        emits = []

        # 0-indexed t2/t4/t6 complete as current=3/5/7 -- all odd.
        failing = {"t2", "t4", "t6"}

        async def _fake_single(ctx, test_id, semaphore, agent, evaluator, **kwargs):
            async with semaphore:
                if test_id in failing:
                    return {
                        "test_id": test_id,
                        "status": "failed",
                        "error": f"boom-{test_id}",
                        "execution_time": 1,
                    }
                return {"test_id": test_id, "status": "succeeded", "execution_time": 1}

        with patch(
            "rhesis.backend.jobs.execution.batch.runner._execute_single_test",
            side_effect=_fake_single,
        ):
            asyncio.run(run_batch(ctx, test_ids, on_emit=lambda m: emits.append(m)))

        failure_lines = [m for m in emits if "failed" in m]
        assert len(failure_lines) == 3
        for tid in failing:
            assert any(f"boom-{tid}" in m for m in failure_lines)

        # The successes are still throttled -- 40 tests must not produce 40 lines.
        assert len(emits) < 40
