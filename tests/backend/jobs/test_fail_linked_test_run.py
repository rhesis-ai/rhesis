"""A task that dies must leave its test run in a terminal state.

The ``job`` row and the ``test_run`` are separate records. Before this hook,
``on_failure`` wrote only the job row, so a task killed outside its own
``except`` -- an OOM kill, a pod eviction, a hard time limit, or a status
write that could not get a connection -- left the run in Progress with
nothing alive to move it and no sweeper to notice. The Summary tab then shows
a run as still executing forever.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/jobs/test_fail_linked_test_run.py -v
"""

from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest

from rhesis.backend.jobs.base import BaseJob
from rhesis.backend.jobs.enums import RunStatus


class _Task(BaseJob):
    """Celery's ``request`` is a read-only property, so override it here."""

    def __init__(self, test_run_id=None):
        self._request = Mock()
        self._request.id = "task-1"
        self._request.headers = {"test_run_id": str(test_run_id)} if test_run_id else {}
        self.get_tenant_context = Mock(return_value=("org-1", "user-1", "proj-1"))
        self.log_with_context = Mock()

    @property
    def request(self):
        return self._request


def _make_task(test_run_id=None):
    """A BaseJob wired with just enough request context for the hook."""
    return _Task(test_run_id)


def _make_run(status_name):
    run = Mock()
    run.status = Mock()
    run.status.name = status_name
    return run


@pytest.fixture
def db_session():
    """A session whose context manager yields a MagicMock."""
    session = MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = Mock(return_value=session)
    ctx.__exit__ = Mock(return_value=False)
    return session, ctx


class TestFailsAnOpenRun:
    def test_marks_a_running_run_failed(self, db_session):
        session, ctx = db_session
        run = _make_run(RunStatus.PROGRESS.value)
        task = _make_task(uuid4())

        with (
            patch("rhesis.backend.app.database.get_db_with_tenant_variables", return_value=ctx),
            patch("rhesis.backend.app.crud.test_run.get_test_run", return_value=run),
            patch("rhesis.backend.jobs.utils.update_test_run_with_error") as update,
        ):
            task._fail_linked_test_run(RuntimeError("worker lost"))

        update.assert_called_once()
        assert "worker lost" in update.call_args[0][2]
        session.commit.assert_called_once()

    def test_also_covers_a_queued_run(self, db_session):
        """Killed before it ever started is still a run that must not hang."""
        session, ctx = db_session
        run = _make_run(RunStatus.QUEUED.value)
        task = _make_task(uuid4())

        with (
            patch("rhesis.backend.app.database.get_db_with_tenant_variables", return_value=ctx),
            patch("rhesis.backend.app.crud.test_run.get_test_run", return_value=run),
            patch("rhesis.backend.jobs.utils.update_test_run_with_error") as update,
        ):
            task._fail_linked_test_run(RuntimeError("evicted"))

        update.assert_called_once()


class TestLeavesTerminalRunsAlone:
    @pytest.mark.parametrize(
        "status",
        [
            RunStatus.CANCELLED.value,
            RunStatus.COMPLETED.value,
            RunStatus.FAILED.value,
            RunStatus.PARTIAL.value,
        ],
    )
    def test_does_not_overwrite(self, db_session, status):
        """Cancelled matters most: the user asked for it, and a task torn
        down mid-cancel must not relabel it Failed."""
        session, ctx = db_session
        run = _make_run(status)
        task = _make_task(uuid4())

        with (
            patch("rhesis.backend.app.database.get_db_with_tenant_variables", return_value=ctx),
            patch("rhesis.backend.app.crud.test_run.get_test_run", return_value=run),
            patch("rhesis.backend.jobs.utils.update_test_run_with_error") as update,
        ):
            task._fail_linked_test_run(RuntimeError("boom"))

        update.assert_not_called()
        session.commit.assert_not_called()


class TestNoLinkedRun:
    def test_skips_entirely_without_a_test_run_id(self):
        """Most job types have no run; the hook must not touch the database."""
        task = _make_task(None)

        with patch("rhesis.backend.app.database.get_db_with_tenant_variables") as get_db:
            task._fail_linked_test_run(RuntimeError("boom"))

        get_db.assert_not_called()

    def test_tolerates_a_deleted_run(self, db_session):
        session, ctx = db_session
        task = _make_task(uuid4())

        with (
            patch("rhesis.backend.app.database.get_db_with_tenant_variables", return_value=ctx),
            patch("rhesis.backend.app.crud.test_run.get_test_run", return_value=None),
            patch("rhesis.backend.jobs.utils.update_test_run_with_error") as update,
        ):
            task._fail_linked_test_run(RuntimeError("boom"))

        update.assert_not_called()


class TestOnFailureWiring:
    def test_permanent_failure_reaches_the_hook(self):
        """The hook is only useful if on_failure actually calls it."""
        task = _make_task(uuid4())
        task._advance_job_row = Mock()
        task._fail_linked_test_run = Mock()
        task._get_execution_time = Mock(return_value="1s")
        task.send_email_notification_flag = False
        task._request.retries = task.max_retries  # out of retries -> permanent

        # Call the real implementation, stubbing only Celery's own super().
        with patch("celery.Task.on_failure", return_value=None):
            BaseJob.on_failure(task, RuntimeError("boom"), "task-1", (), {}, None)

        task._advance_job_row.assert_called_once()
        task._fail_linked_test_run.assert_called_once()

    def test_a_retry_leaves_the_run_alone(self):
        """Still going to run again -- failing the run now would be wrong."""
        task = _make_task(uuid4())
        task._advance_job_row = Mock()
        task._fail_linked_test_run = Mock()
        task._get_execution_time = Mock(return_value="1s")
        task._request.retries = 0

        with patch("celery.Task.on_failure", return_value=None):
            BaseJob.on_failure(task, RuntimeError("boom"), "task-1", (), {}, None)

        task._fail_linked_test_run.assert_not_called()


class TestNeverRaises:
    def test_swallows_its_own_failure(self):
        """This runs inside on_failure. Raising here would replace the real
        error with a bookkeeping one -- the pool being exhausted is exactly
        when this hook is most likely to fail and least allowed to."""
        task = _make_task(uuid4())

        with patch(
            "rhesis.backend.app.database.get_db_with_tenant_variables",
            side_effect=TimeoutError("QueuePool limit reached"),
        ):
            task._fail_linked_test_run(RuntimeError("original"))
