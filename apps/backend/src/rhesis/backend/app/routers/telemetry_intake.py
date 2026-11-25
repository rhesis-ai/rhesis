"""The request side of trace ingest, shared by the SDK and OTLP routes.

Each route takes an admission slot, reads the body under a size cap, does its
CPU work (parsing, translation) in a worker thread, and queues the spans. The
event loop only ever awaits, so a slow or huge export never stalls other
requests, and no database write happens before the response.
"""

import logging
from typing import AsyncIterator, Callable, TypeVar

import anyio
from fastapi import HTTPException, Request

from rhesis.backend.app.config.settings import TraceIngestSettings, get_trace_ingest_settings
from rhesis.backend.app.dependencies import assert_project_access
from rhesis.backend.app.error_handlers import PublicHTTPException
from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.telemetry.admission import (
    InflightSlot,
    IngestRejected,
    Rejection,
    check_org_rate,
    check_queue_depth,
    inflight,
)
from rhesis.backend.app.services.telemetry.ingest import IngestJob

logger = logging.getLogger(__name__)

T = TypeVar("T")

# CPU work for ingest gets its own small pool, so decoding never takes the
# threads FastAPI runs every sync route and dependency on. Two, not more: the
# GIL keeps CPU-bound threads from running in parallel, and more of them only
# starve the threads serving other requests.
_cpu = anyio.CapacityLimiter(2)


def settings() -> TraceIngestSettings:
    return get_trace_ingest_settings()


async def in_thread(fn: Callable[..., T], *args) -> T:
    return await anyio.to_thread.run_sync(fn, *args, limiter=_cpu)


async def _read_body(request: Request, limits: TraceIngestSettings, slot: InflightSlot) -> bytes:
    """The raw body, refused as soon as it passes ``max_body_bytes``."""
    too_large = IngestRejected(
        Rejection(413, f"Body exceeds {limits.max_body_bytes} bytes", limits.retry_after_seconds)
    )
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limits.max_body_bytes:
        raise too_large
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limits.max_body_bytes:
            raise too_large
        slot.add(len(chunk))
        chunks.append(chunk)
    return b"".join(chunks)


async def ingest_slot() -> AsyncIterator[InflightSlot]:
    """Dependency, declared first on the ingest routes: a per-process admission slot.

    FastAPI solves dependencies in order, so the slot is taken before
    authentication and the feature and quota checks, which use the database.
    A burst beyond the process's capacity gets an immediate 503 instead of
    queueing for database connections the rest of the API needs.
    """
    limits = settings()
    try:
        slot = inflight.acquire(limits)
    except IngestRejected as exc:
        raise as_http_exception(exc.rejection) from exc
    try:
        yield slot
    finally:
        inflight.release(slot)


async def admitted_body(
    organization_id: str, request: Request, limits: TraceIngestSettings, slot: InflightSlot
) -> bytes:
    """Read the body under ``slot``, then pass the queue and org rate checks.

    Count any decompressed copy with ``slot.add``.
    """
    body = await _read_body(request, limits, slot)
    await in_thread(check_queue_depth, limits)
    # Last, so a request turned away for a full queue does not use up the org's budget.
    await in_thread(check_org_rate, organization_id, len(body), limits)
    return body


async def enqueue(job: IngestJob, limits: TraceIngestSettings) -> None:
    """Queue ``job`` for a worker. Raises :class:`IngestRejected` (503) if the broker is down."""
    # Imported here: importing jobs builds the Celery app.
    from rhesis.backend.jobs.telemetry import ingest as ingest_jobs

    try:
        # Serializing and compressing the spans is CPU work too.
        await in_thread(ingest_jobs.enqueue_ingest, job, limits.max_message_bytes)
    except Exception as exc:
        logger.error(f"Could not queue {len(job.spans)} span(s) for ingest: {exc}", exc_info=True)
        raise IngestRejected(
            Rejection(503, "Trace ingest is unavailable; retry later", limits.retry_after_seconds)
        ) from exc


def check_project_access(request: Request, current_user: User, project_id: str) -> str:
    """:func:`assert_project_access` on a short session of its own.

    The ingest routes hold no database session, so none is checked out while a
    slow client uploads its body.
    """
    return assert_project_access(request, current_user, project_id)


def as_http_exception(rejection: Rejection) -> HTTPException:
    """The rejection as a response that keeps its message, including for a 503.

    Backpressure is expected, not a fault: the access log records it, so the
    global handler does not log each one again with a stack.
    """
    headers = {"Retry-After": str(rejection.retry_after)} if rejection.status_code != 413 else None
    exc = PublicHTTPException(
        status_code=rejection.status_code, detail=rejection.message, headers=headers
    )
    exc.rhesis_logged = True
    return exc
