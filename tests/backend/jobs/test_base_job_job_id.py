"""``BaseJob`` resolves its ``job`` row id once per run and stamps every event.

The header path is what ``launch_job`` produces; the lookup path covers a
message queued before the header existed. Either way the answer is cached on
the request so a batch narrating thousands of lines pays for it once.
"""

from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from celery.utils.threads import LocalStack

from rhesis.backend.jobs.base import BaseJob

_ORG = "11111111-1111-1111-1111-111111111111"
_USER = "22222222-2222-2222-2222-222222222222"


def _task(headers=None, **request_kwargs) -> BaseJob:
    task = BaseJob()
    task.request_stack = LocalStack()
    task.push_request(
        id="task-1",
        retries=0,
        headers=headers or {},
        kwargs={},
        organization_id=_ORG,
        user_id=_USER,
        **request_kwargs,
    )
    return task


@pytest.mark.unit
class TestResolveJobId:
    def test_reads_the_header_launch_job_sets(self):
        job_id = uuid4()
        task = _task(headers={"job_id": str(job_id)})

        with patch("rhesis.backend.jobs.tracking.get_job_id") as mock_lookup:
            assert task._resolve_job_id() == job_id

        mock_lookup.assert_not_called()

    def test_falls_back_to_one_lookup_and_caches_it(self):
        job_id = uuid4()
        # A registered name, so the tracked-type guard lets the lookup run.
        task = _task()
        task.name = "rhesis.backend.jobs.generate_and_save_test_set"

        with patch("rhesis.backend.jobs.tracking.get_job_id", return_value=job_id) as mock_lookup:
            assert task._resolve_job_id() == job_id
            assert task._resolve_job_id() == job_id
            task.emit("one")
            task.emit("two")

        mock_lookup.assert_called_once_with("task-1", _ORG, _USER, "")

    def test_a_miss_is_cached_too(self):
        task = _task()
        task.name = "rhesis.backend.jobs.generate_and_save_test_set"

        with patch("rhesis.backend.jobs.tracking.get_job_id", return_value=None) as mock_lookup:
            assert task._resolve_job_id() is None
            assert task._resolve_job_id() is None

        mock_lookup.assert_called_once()

    def test_untracked_type_skips_the_lookup(self):
        task = _task()
        task.name = "rhesis.backend.jobs.usage.accrue_usage"

        with patch("rhesis.backend.jobs.tracking.get_job_id") as mock_lookup:
            assert task._resolve_job_id() is None

        mock_lookup.assert_not_called()

    def test_a_bad_header_is_swallowed(self):
        task = _task(headers={"job_id": "not-a-uuid"})

        assert task._resolve_job_id() is None  # must not raise


@pytest.mark.unit
class TestEventsCarryJobId:
    def test_emit_stamps_job_id(self):
        job_id = uuid4()
        task = _task(headers={"job_id": str(job_id)})

        with patch("rhesis.backend.events.emit") as mock_emit:
            task.emit("Generated 5 of 5 tests")

        (event,), _ = mock_emit.call_args
        assert event.job_id == job_id

    def test_emit_passes_a_callers_session_through(self):
        task = _task(headers={"job_id": str(uuid4())})
        sentinel = object()

        with patch("rhesis.backend.events.emit") as mock_emit:
            task.emit("joined", db=sentinel)

        assert mock_emit.call_args.kwargs["db"] is sentinel

    def test_lifecycle_events_stamp_job_id(self):
        job_id = uuid4()
        task = _task(headers={"job_id": str(job_id)})

        with (
            patch("rhesis.backend.events.emit") as mock_emit,
            patch("rhesis.backend.jobs.tracking.mark_running"),
        ):
            task._advance_job_row("running")

        (event,), _ = mock_emit.call_args
        assert event.event_type == "job.started"
        assert isinstance(event.job_id, UUID) and event.job_id == job_id
