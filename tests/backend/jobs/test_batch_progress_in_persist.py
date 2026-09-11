"""Batch mode ticks job progress inside the result's transaction.

Per test, the runner used to open a session for the result, another for
``set_progress``, and two more for the two sinks behind ``on_emit``. The
progress tick now rides in ``persist_result``'s session as one UPDATE, and
the only ``on_progress`` call left is the settling ``(total, total)`` at the
end of the batch.
"""

import asyncio
import uuid
from unittest.mock import MagicMock, call, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.models.job import Job
from rhesis.backend.jobs.execution.batch.persist import _tick_job_progress, persist_result
from rhesis.backend.jobs.execution.batch.runner import run_batch
from tests.backend.fixtures.test_setup import create_test_organization_and_user


def _ctx(test_ids):
    ctx = MagicMock()
    ctx.batch_concurrency = 4
    ctx.per_test_timeout = 60
    ctx.recovery_rounds = 0
    ctx.celery_task_id = "task-1"
    ctx.existing_result_ids = set()
    ctx.test_data = {tid: {"test": MagicMock(category=None)} for tid in test_ids}
    ctx.input_files = {}
    return ctx


@pytest.mark.unit
class TestRunnerNoLongerTicksPerTest:
    def test_run_batch_has_no_progress_callback(self):
        """The per-test callback is gone from the signature, not just unused,
        so a future caller cannot quietly reintroduce a session per test."""
        import inspect

        assert "on_progress" not in inspect.signature(run_batch).parameters

    def test_per_test_completion_only_narrates(self):
        ctx = _ctx(["t1", "t2"])
        emits = []

        async def _fake_single(ctx, test_id, *_args, **_kwargs):
            return {"test_id": test_id, "status": "succeeded", "execution_time": 1}

        with (
            patch(
                "rhesis.backend.jobs.execution.batch.runner._execute_single_test",
                side_effect=_fake_single,
            ),
            patch("rhesis.backend.jobs.tracking.set_progress") as mock_progress,
        ):
            asyncio.run(run_batch(ctx, ["t1", "t2"], on_emit=emits.append))

        mock_progress.assert_not_called()
        assert len(emits) == 2


@pytest.mark.unit
class TestBatchEntrySettlesProgressOnce:
    def test_on_progress_called_once_with_the_total_at_the_end(self):
        from rhesis.backend.jobs.execution.batch import execute_tests_as_batch

        tests = [MagicMock(id="t1"), MagicMock(id="t2"), MagicMock(id="t3")]
        results = [{"test_id": t.id, "status": "succeeded", "execution_time": 1} for t in tests]
        test_run = MagicMock()
        test_run.attributes = {"task_id": "task-1"}
        ctx = MagicMock(
            organization_id="org-1",
            user_id="user-1",
            project_id=None,
            batch_concurrency=1,
            per_test_timeout=30,
            test_data={t.id: {} for t in tests},
        )
        ctx.test_run = test_run
        on_progress = MagicMock()

        with (
            patch(
                "rhesis.backend.jobs.execution.batch.prefetch_execution_context",
                return_value=ctx,
            ),
            patch("rhesis.backend.jobs.execution.shared.update_test_run_start"),
            patch("rhesis.backend.jobs.execution.batch.run_batch", return_value=MagicMock()),
            patch("rhesis.backend.jobs.execution.batch.run_on_thread_loop", return_value=results),
            patch("rhesis.backend.jobs.execution.shared.trigger_results_collection"),
        ):
            execute_tests_as_batch(
                MagicMock(), MagicMock(), test_run, tests, on_progress=on_progress
            )

        assert on_progress.call_args_list == [call(3, 3)]


@pytest.mark.unit
class TestPersistResultTicksInsideTheTransaction:
    def test_tick_happens_before_the_commit_on_the_same_session(self):
        order = []
        session = MagicMock()
        session.commit.side_effect = lambda: order.append("commit")
        ctx = MagicMock(
            organization_id="org-1",
            user_id="user-1",
            project_id=None,
            reference_test_run_id=None,
            celery_task_id="task-1",
        )

        with (
            patch(
                "rhesis.backend.app.database.get_db_with_tenant_variables",
            ) as mock_sessions,
            patch(
                "rhesis.backend.jobs.execution.executors.results.create_test_result_record",
                side_effect=lambda **_: order.append("result"),
            ),
            patch(
                "rhesis.backend.jobs.execution.batch.persist._tick_job_progress",
                side_effect=lambda db, cid: order.append(("tick", db, cid)),
            ),
        ):
            mock_sessions.return_value.__enter__.return_value = session
            persist_result(ctx, "t1", MagicMock(), {}, {}, [], 1.0, False)

        assert order == ["result", ("tick", session, "task-1"), "commit"]
        # One session for the whole thing -- the point of the change.
        mock_sessions.assert_called_once()

    def test_without_a_celery_task_id_nothing_is_written(self):
        db = MagicMock()

        _tick_job_progress(db, None)

        db.query.assert_not_called()


class TestTickJobProgressSql:
    def test_increments_the_row_and_treats_null_as_zero(self, test_db: Session):
        org, user, _ = create_test_organization_and_user(
            test_db, "Tick Org", "tick@batch-test.com", "Tick User"
        )
        celery_task_id = str(uuid.uuid4())
        job = Job(
            organization_id=org.id,
            user_id=user.id,
            celery_task_id=celery_task_id,
            job_type="execute_test_configuration",
            status="running",
        )
        test_db.add(job)
        test_db.flush()
        assert job.progress_current is None

        _tick_job_progress(test_db, celery_task_id)
        _tick_job_progress(test_db, celery_task_id)
        test_db.expire_all()

        assert test_db.query(Job).filter(Job.id == job.id).one().progress_current == 2
