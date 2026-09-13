"""Shared event- and row-construction helpers for the events test suite."""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from rhesis.backend.app.models.job import Job
from rhesis.backend.events.types import ActivityLogged, PlatformEvent


def make_event(context: Optional[dict] = None, **overrides) -> PlatformEvent:
    """An ``ActivityLogged`` with sensible defaults, for tests that only
    care about dispatcher/sink behavior, not any one event type's fields.
    """
    fields = dict(
        occurred_at=datetime.now(timezone.utc),
        organization_id=uuid4(),
        trace_id="a" * 32,
        span_id="b" * 16,
        source="test",
        level="info",
        message="test message",
        context=context,
    )
    fields.update(overrides)
    return ActivityLogged(**fields)


def base_event_fields(**overrides) -> dict:
    """The fields every event type needs, for tests that build several kinds."""
    fields = dict(
        occurred_at=datetime.now(timezone.utc),
        organization_id=uuid4(),
        trace_id="a" * 32,
        span_id="b" * 16,
        source="test",
        celery_task_id="task-with-job-id",
    )
    fields.update(overrides)
    return fields


def make_job_row(db: Session, org, user, celery_task_id: str) -> Job:
    """A running ``job`` row, flushed so it is visible on *db* only."""
    job = Job(
        organization_id=org.id,
        user_id=user.id,
        celery_task_id=celery_task_id,
        job_type="test.job",
        status="running",
    )
    db.add(job)
    db.flush()
    return job
