"""Cooperative cancellation for background jobs.

Cancelling a job or test run only ever calls Celery's revoke() -- there is no
separate "stop now" signal. On a thread pool, revoke() without terminate=True
cannot interrupt work already dispatched to a pool thread; it only marks the
task id in the worker's in-process revoke set. So a job stops only if it is
checking that set itself at a safe point.

Before this, only the parallel/batch path checked (a poll inside the async
gather loop). The sequential path had no check at all, and neither path
updated the test run's terminal status when a cancellation actually happened
mid-flight -- nothing else does, since task_revoked only fires for a task that
had not started yet (see BaseJob's docstring on JobStatus.CANCELLING).
"""

from unittest.mock import AsyncMock, MagicMock, patch

from rhesis.backend.jobs.enums import RunStatus
from rhesis.backend.jobs.execution.shared import is_task_revoked


class TestIsTaskRevoked:
    def test_false_without_a_task_id(self):
        assert is_task_revoked(None) is False
        assert is_task_revoked("") is False

    def test_true_when_in_the_revoke_set(self):
        with patch("celery.worker.state.revoked", {"task-1"}):
            assert is_task_revoked("task-1") is True

    def test_false_when_not_in_the_revoke_set(self):
        with patch("celery.worker.state.revoked", {"some-other-task"}):
            assert is_task_revoked("task-1") is False

    def test_false_outside_a_worker(self):
        """No worker state module importable -- must not raise."""
        with patch.dict("sys.modules", {"celery.worker.state": None}):
            assert is_task_revoked("task-1") is False


class TestMarkTestRunCancelled:
    """The batch path's own write of the terminal status.

    Nothing else does this for a batch stopped mid-flight: the test-run-cancel
    endpoint sets Cancelled eagerly for the case it drives itself, but a job
    cancelled while its batch is already running has no other writer.
    """

    def test_marks_the_test_run_cancelled(self):
        from rhesis.backend.jobs.execution.batch import _mark_test_run_cancelled

        ctx = MagicMock(organization_id="org-1", user_id="user-1", project_id=None)
        ctx.test_run.id = "run-1"

        fake_db = MagicMock()
        fake_test_run = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = fake_test_run

        with (
            patch("rhesis.backend.app.database.get_db_with_tenant_variables") as mock_get_db,
            patch("rhesis.backend.jobs.execution.run.update_test_run_status") as mock_update_status,
        ):
            mock_get_db.return_value.__enter__.return_value = fake_db

            _mark_test_run_cancelled(ctx)

        mock_update_status.assert_called_once_with(
            fake_db, fake_test_run, RunStatus.CANCELLED.value
        )
        fake_db.commit.assert_called_once()

    def test_missing_test_run_is_a_no_op(self):
        """The run may have been hard-deleted between dispatch and cancellation."""
        from rhesis.backend.jobs.execution.batch import _mark_test_run_cancelled

        ctx = MagicMock(organization_id="org-1", user_id="user-1", project_id=None)
        ctx.test_run.id = "run-1"

        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = None

        with (
            patch("rhesis.backend.app.database.get_db_with_tenant_variables") as mock_get_db,
            patch("rhesis.backend.jobs.execution.run.update_test_run_status") as mock_update_status,
        ):
            mock_get_db.return_value.__enter__.return_value = fake_db

            _mark_test_run_cancelled(ctx)

        mock_update_status.assert_not_called()

    def test_failure_does_not_propagate(self):
        """Best-effort, like every other job-tracking write."""
        from rhesis.backend.jobs.execution.batch import _mark_test_run_cancelled

        ctx = MagicMock(organization_id="org-1", user_id="user-1", project_id=None)
        ctx.test_run.id = "run-1"

        with patch(
            "rhesis.backend.app.database.get_db_with_tenant_variables",
            side_effect=RuntimeError("db gone"),
        ):
            _mark_test_run_cancelled(ctx)  # must not raise


class TestBatchSkipsCollectionOnCancellation:
    """execute_tests_as_batch: all-cancelled results mark the run cancelled and
    skip collect_results; an empty batch (no cancellation) does neither."""

    def _run(self, results, tests=None):
        from rhesis.backend.jobs.execution.batch import execute_tests_as_batch

        session = MagicMock()
        test_config = MagicMock()
        test_run = MagicMock()
        test_run.attributes = {"task_id": "task-1"}
        tests = tests if tests is not None else [MagicMock(id="t1"), MagicMock(id="t2")]

        ctx = MagicMock(
            organization_id="org-1",
            user_id="user-1",
            project_id=None,
            batch_concurrency=1,
            per_test_timeout=30,
            test_data={str(t.id): {} for t in tests},
        )
        ctx.test_run = test_run

        with (
            patch(
                "rhesis.backend.jobs.execution.batch.prefetch_execution_context",
                return_value=ctx,
            ),
            patch("rhesis.backend.jobs.execution.shared.update_test_run_start"),
            patch("rhesis.backend.jobs.execution.batch.run_batch", return_value=MagicMock()),
            patch("rhesis.backend.jobs.execution.batch.run_on_thread_loop", return_value=results),
            patch("rhesis.backend.jobs.execution.batch._persist_failed_results"),
            patch("rhesis.backend.jobs.execution.batch._mark_test_run_cancelled") as mock_mark,
            patch(
                "rhesis.backend.jobs.execution.shared.trigger_results_collection"
            ) as mock_trigger,
        ):
            result = execute_tests_as_batch(session, test_config, test_run, tests)

        return result, mock_mark, mock_trigger

    def test_all_cancelled_marks_run_cancelled_and_skips_collection(self):
        results = [
            {"test_id": "t1", "status": "cancelled", "execution_time": 0},
            {"test_id": "t2", "status": "cancelled", "execution_time": 0},
        ]

        result, mock_mark, mock_trigger = self._run(results)

        mock_mark.assert_called_once()
        mock_trigger.assert_not_called()
        assert result["status"] == "cancelled"

    def test_mixed_results_does_not_mark_cancelled(self):
        results = [
            {"test_id": "t1", "status": "succeeded", "execution_time": 10},
            {"test_id": "t2", "status": "cancelled", "execution_time": 0},
        ]

        result, mock_mark, mock_trigger = self._run(results)

        mock_mark.assert_not_called()
        mock_trigger.assert_called_once()
        assert "status" not in result

    def test_empty_batch_skips_collection_without_marking_cancelled(self):
        """An empty batch is not a cancellation -- there is nothing to mark."""
        result, mock_mark, mock_trigger = self._run([], tests=[])

        mock_mark.assert_not_called()
        mock_trigger.assert_not_called()
        assert "status" not in result


class TestSequentialCancellation:
    """execute_tests_sequentially checks the revoke set once per test -- the
    only safe point in a loop that otherwise blocks synchronously per test."""

    def _test_config(self, org_id="org-1"):
        test_config = MagicMock()
        test_config.user_id = None  # takes the simpler default-model branch
        test_config.organization_id = org_id
        test_config.attributes = {}
        return test_config

    def test_revoked_before_the_first_test_runs_none(self):
        from rhesis.backend.jobs.execution.sequential import execute_tests_sequentially

        session = MagicMock()
        test_config = self._test_config()
        test_run = MagicMock()
        test_run.attributes = {"task_id": "task-1"}
        tests = [MagicMock(id="t1"), MagicMock(id="t2")]

        with (
            patch("rhesis.backend.jobs.execution.sequential.update_test_run_start"),
            patch(
                "rhesis.backend.app.utils.user_model_utils.resolve_default_hosted_model",
                return_value="dummy-model",
            ),
            patch(
                "rhesis.backend.jobs.execution.sequential.is_task_revoked",
                return_value=True,
            ),
            patch("rhesis.backend.jobs.execution.sequential.execute_test") as mock_execute_test,
            patch(
                "rhesis.backend.jobs.execution.sequential.update_test_run_status"
            ) as mock_update_status,
            patch(
                "rhesis.backend.jobs.execution.sequential.trigger_results_collection"
            ) as mock_trigger,
        ):
            result = execute_tests_sequentially(session, test_config, test_run, tests)

        mock_execute_test.assert_not_called()
        mock_update_status.assert_called_once_with(session, test_run, RunStatus.CANCELLED.value)
        mock_trigger.assert_not_called()
        assert result["status"] == "cancelled"

    def test_revoked_after_the_first_test_stops_before_the_second(self):
        from rhesis.backend.jobs.execution.sequential import execute_tests_sequentially

        session = MagicMock()
        test_config = self._test_config()
        test_run = MagicMock()
        test_run.attributes = {"task_id": "task-1"}
        tests = [MagicMock(id="t1"), MagicMock(id="t2"), MagicMock(id="t3")]

        with (
            patch("rhesis.backend.jobs.execution.sequential.update_test_run_start"),
            patch(
                "rhesis.backend.app.utils.user_model_utils.resolve_default_hosted_model",
                return_value="dummy-model",
            ),
            patch(
                "rhesis.backend.jobs.execution.sequential.is_task_revoked",
                side_effect=[False, True],
            ),
            patch(
                "rhesis.backend.jobs.execution.sequential.execute_test",
                new_callable=AsyncMock,
                return_value={"test_id": "t1", "status": "succeeded"},
            ) as mock_execute_test,
            patch(
                "rhesis.backend.jobs.execution.sequential.update_test_run_status"
            ) as mock_update_status,
            patch(
                "rhesis.backend.jobs.execution.sequential.trigger_results_collection"
            ) as mock_trigger,
        ):
            result = execute_tests_sequentially(session, test_config, test_run, tests)

        assert mock_execute_test.await_count == 1, "only the first test should have run"
        mock_update_status.assert_called_once_with(session, test_run, RunStatus.CANCELLED.value)
        mock_trigger.assert_not_called()
        assert result["status"] == "cancelled"
        assert result["total_tests"] == len(tests)

    def test_no_revoke_runs_to_completion_as_before(self):
        """Not a new behavior -- pins that the added check doesn't change it."""
        from rhesis.backend.jobs.execution.sequential import execute_tests_sequentially

        session = MagicMock()
        test_config = self._test_config()
        test_run = MagicMock()
        test_run.attributes = {"task_id": "task-1"}
        tests = [MagicMock(id="t1"), MagicMock(id="t2")]

        with (
            patch("rhesis.backend.jobs.execution.sequential.update_test_run_start"),
            patch(
                "rhesis.backend.app.utils.user_model_utils.resolve_default_hosted_model",
                return_value="dummy-model",
            ),
            patch(
                "rhesis.backend.jobs.execution.sequential.is_task_revoked",
                return_value=False,
            ),
            patch(
                "rhesis.backend.jobs.execution.sequential.execute_test",
                new_callable=AsyncMock,
                return_value={"status": "succeeded"},
            ),
            patch(
                "rhesis.backend.jobs.execution.sequential.update_test_run_status"
            ) as mock_update_status,
            patch(
                "rhesis.backend.jobs.execution.sequential.trigger_results_collection",
                return_value=MagicMock(id="collect-task-1"),
            ) as mock_trigger,
        ):
            result = execute_tests_sequentially(session, test_config, test_run, tests)

        mock_update_status.assert_not_called()
        mock_trigger.assert_called_once()
        assert "status" not in result
