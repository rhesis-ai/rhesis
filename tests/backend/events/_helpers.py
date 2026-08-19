"""Shared event-construction helper for the events test suite."""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

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
