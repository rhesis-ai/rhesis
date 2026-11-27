"""Spans queued for storage hold back an evaluation that reads their trace."""

import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from celery.exceptions import Retry
from rhesis.telemetry.schemas import OTELSpan

from rhesis.backend.app.services.telemetry import ingest_pending
from rhesis.backend.app.services.telemetry.ingest import IngestJob, SpanStorageError, StoredBatch
from rhesis.backend.jobs.telemetry import ingest as ingest_jobs

# Bound at import: the autouse inline_trace_ingest fixture replaces the module attribute.
from rhesis.backend.jobs.telemetry.ingest import enqueue_ingest

ORG, PROJECT = "org-1", "project-1"
T1, T2 = "a" * 32, "b" * 32


@pytest.fixture(autouse=True)
def in_memory(monkeypatch):
    cache = ingest_pending.IngestPendingCache()
    cache._initialized = True
    cache._retry_at = float("inf")
    monkeypatch.setattr(ingest_pending, "_cache", cache)
    monkeypatch.setattr(ingest_pending, "_POLL_SECONDS", 0.01)
    return cache


def _span(trace_id: str, span_id: str = "0" * 16) -> OTELSpan:
    now = datetime.now(timezone.utc)
    return OTELSpan(
        trace_id=trace_id,
        span_id=span_id,
        span_name="function.chat",
        start_time=now,
        end_time=now,
    )


def _job(*trace_ids: str) -> IngestJob:
    spans = [_span(t, f"{i:016x}") for i, t in enumerate(trace_ids)]
    return IngestJob(spans, ORG, "user-1", PROJECT)


@pytest.mark.unit
class TestMarks:
    def test_a_trace_is_pending_until_each_message_is_done(self):
        ingest_pending.mark_queued("m1", ORG, PROJECT, ["t1"])
        ingest_pending.mark_queued("m2", ORG, PROJECT, ["t1"])

        ingest_pending.mark_done("m1", ORG, PROJECT, ["t1"])
        assert ingest_pending.is_pending(ORG, PROJECT, "t1")

        ingest_pending.mark_done("m2", ORG, PROJECT, ["t1"])
        assert not ingest_pending.is_pending(ORG, PROJECT, "t1")

    def test_marks_are_kept_per_project(self):
        ingest_pending.mark_queued("m1", ORG, PROJECT, ["t1"])

        assert not ingest_pending.is_pending(ORG, "other-project", "t1")

    def test_the_wait_ends_when_the_spans_are_stored(self):
        ingest_pending.mark_queued("m1", ORG, PROJECT, ["t1"])

        def store():
            ingest_pending.mark_done("m1", ORG, PROJECT, ["t1"])

        with patch.object(ingest_pending.time, "sleep", side_effect=lambda _s: store()):
            assert ingest_pending.wait_until_stored(ORG, PROJECT, "t1", timeout_seconds=5)

    def test_the_wait_gives_up_at_its_limit(self):
        ingest_pending.mark_queued("m1", ORG, PROJECT, ["t1"])

        started = time.monotonic()
        assert not ingest_pending.wait_until_stored(ORG, PROJECT, "t1", timeout_seconds=0.05)
        assert time.monotonic() - started < 1

    def test_nothing_queued_needs_no_wait(self):
        with patch.object(ingest_pending.time, "sleep") as sleep:
            assert ingest_pending.wait_until_stored(ORG, PROJECT, "t1")
        sleep.assert_not_called()


@pytest.mark.unit
class TestTheIngestQueue:
    def test_each_queued_message_marks_its_traces(self):
        with patch.object(ingest_jobs.ingest_spans, "apply_async") as queued:
            enqueue_ingest(_job(T1, T2), max_message_bytes=10**6)

        message = queued.call_args.kwargs["kwargs"]["message"]
        assert message["id"] and message["trace_ids"] == [T1, T2]
        assert ingest_pending.is_pending(ORG, PROJECT, T1)
        assert ingest_pending.is_pending(ORG, PROJECT, T2)

    def test_a_message_the_broker_refused_leaves_no_mark(self):
        with patch.object(ingest_jobs.ingest_spans, "apply_async", side_effect=OSError("down")):
            with pytest.raises(OSError):
                enqueue_ingest(_job(T1), max_message_bytes=10**6)

        assert not ingest_pending.is_pending(ORG, PROJECT, T1)

    def _queued_message(self) -> dict:
        with patch.object(ingest_jobs.ingest_spans, "apply_async") as queued:
            enqueue_ingest(_job(T1), max_message_bytes=10**6)
        return queued.call_args.kwargs["kwargs"]["message"]

    def test_storing_the_spans_clears_the_mark(self):
        message = self._queued_message()

        with (
            patch.object(ingest_jobs, "SessionLocal", return_value=MagicMock()),
            patch.object(ingest_jobs, "bind_scope_to_session"),
            patch.object(ingest_jobs, "process_ingest_job", return_value=StoredBatch([], [])),
        ):
            ingest_jobs.ingest_spans.run(message)

        assert not ingest_pending.is_pending(ORG, PROJECT, T1)

    def test_a_retried_message_keeps_its_mark(self):
        message = self._queued_message()

        with (
            patch.object(ingest_jobs, "SessionLocal", return_value=MagicMock()),
            patch.object(ingest_jobs, "bind_scope_to_session"),
            patch.object(
                ingest_jobs, "process_ingest_job", side_effect=SpanStorageError("db blip")
            ),
            patch.object(ingest_jobs.ingest_spans, "retry", side_effect=Retry()),
        ):
            with pytest.raises(Retry):
                ingest_jobs.ingest_spans.run(message)

        assert ingest_pending.is_pending(ORG, PROJECT, T1)
