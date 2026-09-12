"""Sequential mode commits before every test so its connection is not left
"idle in transaction" across the LLM call and evaluation.

The run's one session is shared with ``execute_test``; with autocommit off,
whatever the previous test left open would otherwise stay open for the whole
next test, holding a pool slot and a vacuum horizon for minutes.
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError, PendingRollbackError

from rhesis.backend.jobs.enums import RunStatus
from rhesis.backend.jobs.execution.sequential import execute_tests_sequentially


def _config():
    cfg = MagicMock()
    cfg.id = "cfg-1"
    cfg.organization_id = "org-1"
    cfg.user_id = "user-1"
    cfg.endpoint_id = "ep-1"
    cfg.attributes = {}
    return cfg


def _run():
    run = MagicMock()
    run.id = "run-1"
    run.attributes = {"task_id": "task-1"}
    return run


@pytest.mark.unit
class TestCommitBeforeEachTest:
    def test_commits_right_before_every_execute_test(self):
        order = []
        session = MagicMock()
        session.commit.side_effect = lambda: order.append("commit")
        tests = [MagicMock(id=f"t{i}") for i in range(3)]

        async def _fake_execute(**kwargs):
            order.append(("execute", kwargs["test_id"]))
            return {"test_id": kwargs["test_id"], "status": "succeeded"}

        with (
            patch(
                "rhesis.backend.jobs.execution.sequential.execute_test",
                side_effect=_fake_execute,
            ),
            patch("rhesis.backend.jobs.execution.sequential.update_test_run_start"),
            patch(
                "rhesis.backend.jobs.execution.sequential.trigger_results_collection",
                return_value=MagicMock(id="collect-1"),
            ),
            patch("rhesis.backend.jobs.execution.sequential.is_task_revoked", return_value=False),
        ):
            execute_tests_sequentially(session, _config(), _run(), tests)

        # The model-resolution block may commit on its own through mocks; what
        # matters is that each execute is immediately preceded by a commit.
        for i, step in enumerate(order):
            if isinstance(step, tuple) and step[0] == "execute":
                assert i > 0 and order[i - 1] == "commit", f"no commit right before {step}"
        assert sum(1 for s in order if isinstance(s, tuple)) == 3

    def test_the_session_object_stays_the_one_execute_test_receives(self):
        """Committing must not swap or close the session: expire_on_commit is
        off on SessionLocal, and the ORM objects keep being used after it."""
        session = MagicMock()
        seen = []

        async def _fake_execute(**kwargs):
            seen.append(kwargs["db"])
            return {"test_id": kwargs["test_id"], "status": "succeeded"}

        with (
            patch(
                "rhesis.backend.jobs.execution.sequential.execute_test",
                side_effect=_fake_execute,
            ),
            patch("rhesis.backend.jobs.execution.sequential.update_test_run_start"),
            patch(
                "rhesis.backend.jobs.execution.sequential.trigger_results_collection",
                return_value=MagicMock(id="collect-1"),
            ),
            patch("rhesis.backend.jobs.execution.sequential.is_task_revoked", return_value=False),
        ):
            execute_tests_sequentially(session, _config(), _run(), [MagicMock(id="t1")])

        assert seen == [session]
        session.close.assert_not_called()


@pytest.mark.unit
class TestDatabaseErrorStaysOneTestsOwn:
    """A database error on one test must not take the rest of the run with it.

    The per-test commit above only holds if the session is usable when the next
    iteration reaches it. ``execute_test`` writes results on that same session, so
    a failed write leaves it needing a rollback -- and an un-rolled-back session
    raises ``PendingRollbackError`` on the next commit, outside any handler.
    """

    @staticmethod
    def _session_that_needs_a_rollback():
        """A session that behaves like psycopg2's after a failed statement."""
        session = MagicMock()
        state = {"broken": False}

        def _commit():
            if state["broken"]:
                raise PendingRollbackError(
                    "This Session's transaction has been rolled back due to a previous "
                    "exception during flush."
                )

        def _rollback():
            state["broken"] = False

        session.commit.side_effect = _commit
        session.rollback.side_effect = _rollback
        return session, state

    def _execute(self, session, state, failing_index: int, total: int):
        executed = []

        async def _fake_execute(**kwargs):
            executed.append(kwargs["test_id"])
            if kwargs["test_id"] == f"t{failing_index}":
                state["broken"] = True
                raise OperationalError("INSERT INTO test_result ...", {}, Exception("boom"))
            return {"test_id": kwargs["test_id"], "status": "succeeded"}

        collection = MagicMock(id="collect-1")
        with (
            patch(
                "rhesis.backend.jobs.execution.sequential.execute_test",
                side_effect=_fake_execute,
            ),
            patch("rhesis.backend.jobs.execution.sequential.update_test_run_start"),
            patch(
                "rhesis.backend.jobs.execution.sequential.trigger_results_collection",
                return_value=collection,
            ) as trigger,
            patch("rhesis.backend.jobs.execution.sequential.is_task_revoked", return_value=False),
        ):
            outcome = execute_tests_sequentially(
                session,
                _config(),
                _run(),
                [MagicMock(id=f"t{i}") for i in range(1, total + 1)],
            )
        return executed, trigger, outcome

    def test_later_tests_still_run_and_the_run_finishes(self):
        session, state = self._session_that_needs_a_rollback()
        executed, trigger, outcome = self._execute(session, state, failing_index=2, total=4)

        # Every test after the failure was still attempted.
        assert executed == ["t1", "t2", "t3", "t4"]
        session.rollback.assert_called_once()

        # The run reached its terminal handoff with a row for all four tests,
        # the failed one included.
        trigger.assert_called_once()
        results = trigger.call_args[0][2]
        assert [r["test_id"] for r in results] == ["t1", "t2", "t3", "t4"]
        assert results[1]["status"] == "failed"
        assert results[1]["exception_type"] == "OperationalError"
        assert outcome["total_tests"] == 4

    def test_cancelled_run_after_a_failure_still_records_its_status(self):
        """The cancel path commits too, so it needs the same usable session."""
        session, state = self._session_that_needs_a_rollback()
        revoked = iter([False, False, True])

        async def _fake_execute(**kwargs):
            if kwargs["test_id"] == "t2":
                state["broken"] = True
                raise OperationalError("INSERT INTO test_result ...", {}, Exception("boom"))
            return {"test_id": kwargs["test_id"], "status": "succeeded"}

        with (
            patch(
                "rhesis.backend.jobs.execution.sequential.execute_test",
                side_effect=_fake_execute,
            ),
            patch("rhesis.backend.jobs.execution.sequential.update_test_run_start"),
            patch(
                "rhesis.backend.jobs.execution.sequential.trigger_results_collection",
                return_value=MagicMock(id="collect-1"),
            ),
            patch(
                "rhesis.backend.jobs.execution.sequential.is_task_revoked",
                side_effect=lambda _task_id: next(revoked),
            ),
            patch(
                "rhesis.backend.jobs.execution.sequential.update_test_run_status"
            ) as update_status,
        ):
            outcome = execute_tests_sequentially(
                session,
                _config(),
                _run(),
                [MagicMock(id=f"t{i}") for i in range(1, 4)],
            )

        update_status.assert_called_once()
        assert update_status.call_args[0][2] == RunStatus.CANCELLED.value
        assert outcome["status"] == "cancelled"
