"""Sink registry and delivery policy. See ``events-layer.md`` in the design
docs for the contract this implements; summarized here in the parts that are
easy to get wrong.

``emit()`` is synchronous -- not queued, not threaded. A future audit sink
needs to join the caller's transaction, which is impossible if delivery is
deferred. A sink that needs batching does it internally, the same way
``BatchSpanProcessor`` already does for the tracer.
"""

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.events.redaction import redact_metadata
from rhesis.backend.events.sinks.base import Sink
from rhesis.backend.events.types import PlatformEvent

logger = logging.getLogger(__name__)

_sinks: List[Sink] = []


def register_sink(sink: Sink) -> None:
    """Add a sink to the registry.

    Registration order is the delivery order and nothing more should be
    inferred from it -- there is no ordering guarantee across sinks. Within
    ``activity_log``, ordering comes from the ``sequence`` column, not from
    delivery timing.
    """
    _sinks.append(sink)


def _redact(event: PlatformEvent) -> PlatformEvent:
    """Redaction runs once, here, before any sink sees the event -- never per
    sink, which fails open the moment someone adds a sink and forgets.

    ``PlatformEvent`` is frozen, so a redacted copy is returned rather than
    mutating in place; unchanged events skip the copy.
    """
    if not event.context:
        return event
    redacted_context = redact_metadata(event.context)
    if redacted_context == event.context:
        return event
    return event.model_copy(update={"context": redacted_context})


def emit(event: PlatformEvent, *, db: Optional[Session] = None) -> None:
    """Dispatch ``event`` to every registered sink that handles it.

    ``db``, when given, is for a sink that needs to join the caller's
    transaction (a future critical audit sink -- see ``sinks/base.py``). No
    sink shipped today reads it; the parameter exists now because adding
    that sink later must not mean changing every call site's signature.

    Sinks are isolated from each other: one raising does not stop later
    sinks from receiving the event. ``critical`` decides what a failure
    means -- a dropped log line must never fail the work it was describing,
    but a compliance record that silently failed to write is worse than a
    failed request. No retries here; retry policy belongs to the sink that
    knows what its own backend can promise.

    Also writes a DEBUG line so stdout keeps the full narrative -- events
    feed the logger, never the reverse.
    """
    event = _redact(event)
    logger.debug(
        f"event={event.event_type} source={event.source} "
        f"org={event.organization_id} celery_task_id={event.celery_task_id}"
    )

    for sink in _sinks:
        if not sink.handles(event):
            continue
        try:
            sink.deliver(event, db)
        except Exception:
            if sink.critical:
                raise
            logger.exception(f"Sink {sink.name!r} failed to deliver {event.event_type!r}")
