"""Adding destinations, and delivering the audit log to them.

Delivery, per destination: lock its row (``SKIP LOCKED``, so overlapping runs
never send the same batch twice at once), read up to ``BATCH_SIZE`` events
after its cursor, send them, and only then move the cursor, all in one
transaction. A failed send leaves the cursor where it was, so the same events
go again after a backoff: at least once, never skipped.

Backoff after the n-th failure in a row is ``BACKOFF_BASE_SECONDS * 2**(n-1)``,
capped at ``BACKOFF_MAX_SECONDS``. After ``AUTO_PAUSE_AFTER`` failures in a row
(about 13 hours) the destination pauses itself; resuming it picks up at the
cursor, so nothing recorded meanwhile is lost.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.database import SessionLocal, get_db_with_tenant_variables
from rhesis.backend.app.features import FeatureName, FeatureRegistry
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.utils import webhooks
from rhesis.backend.app.utils.ssrf_http_client import SSRFError
from rhesis.backend.ee.audit.schemas import AuditEventRead
from rhesis.backend.ee.audit.streaming import crud
from rhesis.backend.ee.audit.streaming.adapters import KINDS, TEST_TYPE, Batch, DeliveryError
from rhesis.backend.ee.audit.streaming.models import AuditDestination
from rhesis.backend.ee.audit.streaming.schemas import (
    DestinationCreate,
    DestinationCreated,
    DestinationRead,
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 100
MAX_BATCHES_PER_RUN = 10
LAG_SECONDS = 5.0
BACKOFF_BASE_SECONDS = 30
BACKOFF_MAX_SECONDS = 3600
AUTO_PAUSE_AFTER = 20
ERROR_CHARS = 500

PAUSED_MANUAL = "manual"
PAUSED_FAILURES = "failures"


class InvalidDestination(ValueError):
    """The destination cannot be saved as given."""


# ---------------------------------------------------------------------------
# Managing destinations
# ---------------------------------------------------------------------------


def config_of(destination: AuditDestination) -> dict:
    return json.loads(destination.config)


def to_read(destination: AuditDestination) -> DestinationRead:
    config = config_of(destination)
    public = {key: config[key] for key in KINDS[destination.kind].public}
    return DestinationRead(
        id=destination.id,
        name=destination.name,
        kind=destination.kind,
        settings=public,
        paused=destination.paused,
        paused_reason=destination.paused_reason,
        delivered_through=destination.cursor_recorded_at,
        last_success_at=destination.last_success_at,
        last_error=destination.last_error,
        last_error_at=destination.last_error_at,
        consecutive_failures=destination.consecutive_failures,
        next_attempt_at=destination.next_attempt_at,
        created_at=destination.created_at,
    )


def _config(payload: DestinationCreate) -> dict:
    config = payload.model_dump(exclude={"kind", "name"})
    if "url" in config:
        try:
            webhooks.check_destination_url(config["url"])
        except SSRFError as exc:
            raise InvalidDestination(str(exc)) from exc
    if payload.kind == "webhook":
        config["secret"] = webhooks.generate_secret()
    return config


def create_destination(
    db: Session, organization_id: str, payload: DestinationCreate
) -> DestinationCreated:
    """Add a destination. It starts with events recorded from now on."""
    config = _config(payload)
    destination = crud.create_destination(
        db,
        AuditDestination(
            organization_id=organization_id,
            name=payload.name,
            kind=payload.kind,
            config=json.dumps(config),
            cursor_recorded_at=crud.transaction_start(db),
            cursor_id=uuid.UUID(int=0),
        ),
    )
    return DestinationCreated(
        **to_read(destination).model_dump(), signing_secret=config.get("secret")
    )


def set_paused(destination: AuditDestination, paused: bool) -> None:
    """Pause, or resume from the cursor with the failure count reset."""
    destination.paused = paused
    destination.paused_reason = PAUSED_MANUAL if paused else None
    destination.next_attempt_at = None
    if not paused:
        destination.consecutive_failures = 0


def send_test_event(destination: AuditDestination) -> Optional[str]:
    """Send one sample event, outside the log and the cursor. The error, or None."""
    now = datetime.now(timezone.utc)
    sample = AuditEventRead(
        id=uuid.uuid4(),
        organization_id=destination.organization_id,
        occurred_at=now,
        recorded_at=now,
        action=TEST_TYPE,
        outcome="success",
        actor_type="system",
        channel="api",
        trace_id="0" * 32,
        span_id="0" * 16,
        changes=[],
    ).model_dump(mode="json")
    try:
        _send(destination, [sample], test=True)
    except DeliveryError as exc:
        return str(exc)[:ERROR_CHARS]
    return None


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------


def event_payload(row) -> dict:
    """An event exactly as ``GET /audit-events`` lists it.

    The IP is already masked when the org masks IPs (the sink stores it that way).
    Content values are never streamed, even when the org records them: they stay
    behind ``GET /audit-events/{id}``.
    """
    return AuditEventRead.model_validate(row).model_dump(mode="json")


def backoff(failures: int) -> timedelta:
    return timedelta(seconds=min(BACKOFF_BASE_SECONDS * 2 ** (failures - 1), BACKOFF_MAX_SECONDS))


def _send(destination: AuditDestination, events: list[dict], test: bool = False) -> None:
    batch = Batch(str(destination.organization_id), str(destination.id), events, test)
    KINDS[destination.kind].send(config_of(destination), batch)


def _record_failure(destination: AuditDestination, error: str, now: datetime) -> None:
    destination.consecutive_failures += 1
    destination.last_error = error[:ERROR_CHARS]
    destination.last_error_at = now
    if destination.consecutive_failures >= AUTO_PAUSE_AFTER:
        destination.paused = True
        destination.paused_reason = PAUSED_FAILURES
        destination.next_attempt_at = None
    else:
        destination.next_attempt_at = now + backoff(destination.consecutive_failures)


def deliver_batch(db: Session, destination: AuditDestination) -> Optional[int]:
    """Send the next batch. How many events went, or None when the send failed."""
    before = crud.safe_bound(db, LAG_SECONDS)
    cursor = (destination.cursor_recorded_at, destination.cursor_id)
    rows = crud.events_after(db, destination.organization_id, cursor, before, BATCH_SIZE)
    if not rows:
        return 0
    now = datetime.now(timezone.utc)
    try:
        _send(destination, [event_payload(row) for row in rows])
    except Exception as exc:
        expected = isinstance(exc, DeliveryError)
        # Shown to the org's admins, so a bug's details stay in the log.
        error = str(exc) if expected else f"Unexpected error ({type(exc).__name__})"
        logger.warning(f"Audit stream {destination.id} failed: {error}", exc_info=not expected)
        _record_failure(destination, error, now)
        return None
    destination.cursor_recorded_at, destination.cursor_id = rows[-1].recorded_at, rows[-1].id
    destination.consecutive_failures = 0
    destination.next_attempt_at = None
    destination.last_success_at = now
    return len(rows)


def run_destination(db: Session, destination_id) -> None:
    """Deliver batches until caught up, failed, or ``MAX_BATCHES_PER_RUN`` sent."""
    for _ in range(MAX_BATCHES_PER_RUN):
        destination = crud.lock_due_destination(db, destination_id)
        if destination is None:  # paused, backing off, deleted, or another run holds it
            return
        sent = deliver_batch(db, destination)
        db.commit()
        if sent is None or sent < BATCH_SIZE:
            return


def _entitled_organization_ids() -> list[str]:
    with SessionLocal() as db:
        return [
            str(org.id)
            for org in db.query(Organization).all()
            if FeatureRegistry.is_available(FeatureName.AUDIT_LOG, org)
        ]


def deliver_all() -> None:
    """One pass over every entitled org's due destinations. What the beat job runs."""
    for organization_id in _entitled_organization_ids():
        try:
            with get_db_with_tenant_variables(organization_id) as db:
                for destination_id in crud.due_destination_ids(db):
                    run_destination(db, destination_id)
        except Exception:
            logger.exception(f"Audit streaming failed for org {organization_id}")
