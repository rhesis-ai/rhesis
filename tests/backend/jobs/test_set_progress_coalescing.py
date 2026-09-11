"""``BaseJob.set_progress`` writes at most once per second per task run.

A run's progress used to hit the ``job`` row once per finished test, each on
its own session. The bar only needs to move about once a second, but the
first write (which carries ``total``) and the terminal ``current == total``
write must never be dropped.
"""

from unittest.mock import patch

import pytest
from celery.utils.threads import LocalStack

from rhesis.backend.jobs import base
from rhesis.backend.jobs.base import BaseJob

_ORG = "11111111-1111-1111-1111-111111111111"
_USER = "22222222-2222-2222-2222-222222222222"

_TRACKING = "rhesis.backend.jobs.tracking.set_progress"


def _task() -> BaseJob:
    task = BaseJob()
    task.request_stack = LocalStack()
    task.push_request(
        id="task-1", retries=0, headers={}, kwargs={}, organization_id=_ORG, user_id=_USER
    )
    return task


def _written(mock) -> list:
    return [(c.kwargs["current"], c.kwargs["total"]) for c in mock.call_args_list]


@pytest.mark.unit
class TestSetProgressCoalescing:
    def test_first_write_lands_and_a_burst_is_collapsed(self):
        task = _task()

        with patch(_TRACKING) as mock_write:
            for i in range(0, 50):
                task.set_progress(i, 100)

        assert _written(mock_write) == [(0, 100)]

    def test_terminal_write_always_lands(self):
        task = _task()

        with patch(_TRACKING) as mock_write:
            task.set_progress(0, 3)
            task.set_progress(1, 3)
            task.set_progress(2, 3)
            task.set_progress(3, 3)

        assert _written(mock_write) == [(0, 3), (3, 3)]

    def test_writes_again_once_the_interval_has_passed(self):
        task = _task()

        with patch(_TRACKING) as mock_write:
            task.set_progress(0, 10)
            # Age the last write past the interval instead of sleeping.
            task.request.progress_written_at -= base.PROGRESS_WRITE_INTERVAL_S + 0.01
            task.set_progress(4, 10)
            task.set_progress(5, 10)

        assert _written(mock_write) == [(0, 10), (4, 10)]

    def test_state_is_per_task_run(self):
        """A retry gets a fresh request, so the first write of the new run
        must land regardless of when the old run last wrote."""
        first = _task()
        second = _task()

        with patch(_TRACKING) as mock_write:
            first.set_progress(0, 10)
            second.set_progress(0, 10)

        assert _written(mock_write) == [(0, 10), (0, 10)]
