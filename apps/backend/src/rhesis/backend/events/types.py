"""``PlatformEvent``, closed and typed.

A discriminated union, not one class with a payload dict: a base model plus
one subclass per event type, on a ``Literal`` discriminator. A field has to be
declared by a human before it can carry anything, checked at authoring time
rather than by a runtime filter. That is also what stops this becoming a
generic event bus -- adding an event type means adding a subclass here and
nothing else; there is no ``**kwargs`` escape hatch for a call site to widen.

``job_id`` lives on the base and is optional. A caller that already knows
the ``job`` row (``launch_job`` just created it; ``BaseJob`` resolves it once
per task run from the dispatch headers) stamps it so every sink can skip the
``celery_task_id`` -> ``job`` lookup, which used to cost each sink a session
per event. A caller that does not know it leaves it ``None`` and sinks fall
back to that lookup -- so building an event never requires a query.

``JobProgressed`` is intentionally not defined yet: nothing consumes it until
a WebSocket sink ships, and an event type with no sink is dead code with no
test that can prove it works.
"""

import ipaddress
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Tuple
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    IPvAnyAddress,
    JsonValue,
    field_validator,
    model_validator,
)

from rhesis.backend.app.provenance import ActorType, Channel

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
    # The job row this event belongs to, when the emitter already knows it.
    # See the module docstring; sinks resolve it from celery_task_id if None.
    job_id: Optional[UUID] = None

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

    Not named ``JobLogged``: a service with no job can still write one, so
    neither ``celery_task_id`` nor ``job_id`` is required here -- unlike the
    job-lifecycle events above, which always come from a worker. See
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


# ``resource.verb_past``, e.g. ``endpoint.updated``. See ``audit_actions.py``.
AUDIT_ACTION_PATTERN = r"^[a-z][a-z_]*\.[a-z][a-z_]*$"


class FieldChange(BaseModel):
    """One column's change on an audited row.

    ``kind`` decides what is kept. ``value`` records before and after.
    ``secret`` (an ``EncryptedString`` column) records only that the field
    changed. ``content`` carries the values to the audit sink, which stores
    them encrypted when the org opted in and drops them otherwise.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str
    kind: Literal["value", "secret", "content"]
    before: JsonValue = None
    after: JsonValue = None

    @model_validator(mode="after")
    def _secret_has_no_values(self) -> "FieldChange":
        if self.kind == "secret" and (self.before is not None or self.after is not None):
            raise ValueError(f"secret field {self.field!r} must not carry values")
        return self


class ChangeSummary(BaseModel):
    """Creates of one resource type by one job transaction, as a single row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    count: int = Field(ge=1)
    # Empty when there are too many to list; ``count`` is always exact.
    ids: Tuple[UUID, ...] = ()


class AuditRecorded(PlatformEvent):
    """One audit log entry: who did what, to which resource, and what changed.

    ``user_id`` is the actor's user (the token or client owner for
    credentials) and ``entity_id`` the resource. The resource type is the part
    of ``action`` before the dot, so ``entity_type`` may only repeat it.
    """

    event_type: Literal["audit.recorded"] = "audit.recorded"

    action: str = Field(pattern=AUDIT_ACTION_PATTERN)
    outcome: Literal["success", "failure", "denied"]
    status_code: Optional[int] = None

    actor_type: ActorType
    actor_credential_id: Optional[str] = None
    actor_credential_hint: Optional[str] = None
    # Name and email at the time, so the entry still reads after a deletion.
    actor_label: Optional[str] = None
    channel: Channel
    ip: Optional[IPvAnyAddress] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None

    resource_label: Optional[str] = None
    changes: Tuple[FieldChange, ...] = ()
    summary: Optional[ChangeSummary] = None

    @field_validator("ip", mode="before")
    @classmethod
    def _drop_unparseable_ip(cls, value: Any) -> Any:
        # Provenance can hold a placeholder ("testclient", "unknown"), not an address.
        if isinstance(value, str):
            try:
                ipaddress.ip_address(value)
            except ValueError:
                return None
        return value

    @model_validator(mode="after")
    def _consistent(self) -> "AuditRecorded":
        resource = self.action.split(".", 1)[0]
        if self.entity_type is not None and self.entity_type != resource:
            raise ValueError(f"entity_type {self.entity_type!r} does not match {self.action!r}")
        if self.changes and self.summary is not None:
            raise ValueError("an audit event has field changes or a summary, not both")
        return self
