"""Sequential mode commits before every test so its connection is not left
"idle in transaction" across the LLM call and evaluation.

The run's one session is shared with ``execute_test``; with autocommit off,
whatever the previous test left open would otherwise stay open for the whole
next test, holding a pool slot and a vacuum horizon for minutes.
"""

from unittest.mock import MagicMock, patch

import pytest

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
                assert order[i - 1] == "commit", f"no commit right before {step}"
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
