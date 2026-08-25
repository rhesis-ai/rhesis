"""collect_results publishes one last grid tick after the terminal status.

Every other TestRunProgressed comes from an in-flight phase transition, and
the last of those fires while the run is still in Progress. Without a tick
from here the final coalesced publish reports the run as running, and a
client that stops refetching on ``is_terminal`` never learns it finished.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from rhesis.backend.events.types import TestRunProgressed
from rhesis.backend.jobs.execution.results import _emit_terminal_tick


@pytest.mark.unit
class TestTerminalTick:
    def _task(self):
        task = MagicMock()
        task.request.id = "celery-task-1"
        return task

    def test_emits_a_completed_tick_for_the_run(self):
        test_run = MagicMock()
        test_run.id = uuid4()
        org_id = str(uuid4())

        with patch("rhesis.backend.events.emit") as mock_emit:
            _emit_terminal_tick(self._task(), test_run, org_id, None, None, total=7)

        mock_emit.assert_called_once()
        event = mock_emit.call_args.args[0]
        assert isinstance(event, TestRunProgressed)
        assert event.entity_type == "test_run"
        assert event.entity_id == test_run.id
        assert event.source == "collect_results"
        # completed == total is what flips the grid's progress readout to done.
        assert event.completed == 7
        assert event.total == 7
        assert event.generating_test_ids == []
        assert event.evaluating_test_ids == []

    def test_carries_project_and_user_when_present(self):
        test_run = MagicMock()
        test_run.id = uuid4()
        org_id, user_id, project_id = str(uuid4()), str(uuid4()), str(uuid4())

        with patch("rhesis.backend.events.emit") as mock_emit:
            _emit_terminal_tick(self._task(), test_run, org_id, user_id, project_id, total=1)

        event = mock_emit.call_args.args[0]
        assert str(event.organization_id) == org_id
        assert str(event.user_id) == user_id
        assert str(event.project_id) == project_id

    def test_emit_failure_does_not_propagate(self):
        """A dropped live-update push must never fail the results task that
        already wrote the run's terminal status.
        """
        test_run = MagicMock()
        test_run.id = uuid4()

        with patch("rhesis.backend.events.emit", side_effect=RuntimeError("redis down")):
            _emit_terminal_tick(self._task(), test_run, str(uuid4()), None, None, total=1)
