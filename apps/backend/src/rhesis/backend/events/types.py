"""``PlatformEvent``, closed and typed.

A discriminated union, not one class with a payload dict: a base model plus
one subclass per event type, on a ``Literal`` discriminator. A field has to be
declared by a human before it can carry anything, checked at authoring time
rather than by a runtime filter. That is also what stops this becoming a
generic event bus -- adding an event type means adding a subclass here and
nothing else; there is no ``**kwargs`` escape hatch for a call site to widen.

``job_id`` is deliberately absent from every subclass below. Job-lifecycle
events carry ``celery_task_id`` (already on the base, "set when emitted from
a worker") and a sink resolves the ``job`` row from that when it needs the
FK -- the same indexed lookup ``crud.job.get_job_by_celery_task_id`` uses.
That keeps event construction cheap (no query needed to build one) and gives
every sink one join key instead of two.

``JobProgressed`` is intentionally not defined yet: nothing consumes it until
a WebSocket sink ships, and an event type with no sink is dead code with no
test that can prove it works.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

_HEX32 = r"^[0-9a-f]{32}$"
_HEX16 = r"^[0-9a-f]{16}$"


class PlatformEvent(BaseModel):
    """Shared identity, correlation and scope. Every subclass adds only what
    is specific to that moment.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: str
    occurred_at: datetime

    organization_id: UUID
    project_id: Optional[UUID] = None
    user_id: Optional[UUID] = None  # None for system-initiated work

    # W3C trace context. See events/correlation.py for where these come from
    # -- never minted by hand at a call site.
    trace_id: str = Field(pattern=_HEX32)
    span_id: str = Field(pattern=_HEX16)
    celery_task_id: Optional[str] = None

    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    source: str

    # Structured extra data only -- identifiers and counts, never payloads.
    # Redacted once, in the dispatcher, before any sink sees it. Most events
    # need nothing here; it exists because ActivityLog.context (and, later,
    # an audit sink) need somewhere to put small structured attributes that
    # don't warrant their own typed field.
    context: Optional[Dict[str, Any]] = None


class JobQueued(PlatformEvent):
    event_type: Literal["job.queued"] = "job.queued"
    job_type: str
    name: Optional[str] = None


class JobStarted(PlatformEvent):
    event_type: Literal["job.started"] = "job.started"


class JobCompleted(PlatformEvent):
    event_type: Literal["job.completed"] = "job.completed"


class JobFailed(PlatformEvent):
    event_type: Literal["job.failed"] = "job.failed"
    error_type: str
    error_message: str


class JobRetried(PlatformEvent):
    event_type: Literal["job.retried"] = "job.retried"
    attempt: int


class JobCancelled(PlatformEvent):
    event_type: Literal["job.cancelled"] = "job.cancelled"


class ActivityLogged(PlatformEvent):
    """A free-standing log line, from ``self.emit()`` or any service.

    Not named ``JobLogged``: ``celery_task_id`` (and therefore the resolved
    ``job_id``) is optional here specifically, unlike the job-lifecycle
    events above, so a service with no job can still write one. See
    ``README.md``'s "two layers, not one" section.
    """

    event_type: Literal["activity.logged"] = "activity.logged"
    level: Literal["info", "warning", "error"]
    message: str


class TestRunProgressed(PlatformEvent):
    """Coalesced grid tick -- counters and bounded in-flight ids only.

    No per-verdict detail: the client refetches the verdict-matrix endpoint
    on receipt instead of patching state from the payload. See TestRunSink.
    """

    event_type: Literal["test_run.progressed"] = "test_run.progressed"
    completed: int
    total: int
    generating_test_ids: List[UUID] = Field(default_factory=list)
    evaluating_test_ids: List[UUID] = Field(default_factory=list)
