"""Temporary request-vs-DB timing probe for diagnosing the /tests latency gap.

Per-query timing (see the reverted debug_sql_timing.py probe, commit
57ed58154) already includes network round-trip time, since cursor.execute()
blocks until Postgres responds. It does NOT explain time spent outside DB
calls entirely -- ORM row hydration, connection-pool checkout wait, and
per-request auth/dependency overhead (e.g. require_permission's authorize()
check). This module measures that directly, on the same request, instead of
correlating two separately-captured logs.

Enable with RHESIS_ENABLE_REQUEST_TIMING=1. Logs one line per request:

    GET /tests total=2190.3ms db=1181.4ms(17q) other=1008.9ms

Not meant to run in production long-term -- remove once the gap is
diagnosed, same as the SQL timing probe it complements.
"""

import logging
import os
import time
from contextvars import ContextVar

from sqlalchemy import event

from rhesis.backend.app.database import engine

logger = logging.getLogger("request_timing")

_query_durations_ms: ContextVar[list | None] = ContextVar("_query_durations_ms", default=None)


def is_enabled() -> bool:
    return os.environ.get("RHESIS_ENABLE_REQUEST_TIMING", "").lower() in ("1", "true")


@event.listens_for(engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("_query_start_times", []).append(time.perf_counter())


@event.listens_for(engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    start_times = conn.info.get("_query_start_times")
    if not start_times:
        return
    elapsed_ms = (time.perf_counter() - start_times.pop()) * 1000
    durations = _query_durations_ms.get()
    if durations is not None:
        durations.append(elapsed_ms)


class RequestTimingMiddleware:
    """Logs total/db/other wall-clock time for each request.

    Plain ASGI middleware rather than BaseHTTPMiddleware -- the latter runs
    the downstream app in a background task via call_next(), and if the
    server-side connection gets cancelled (e.g. a reverse proxy recycling its
    upstream keep-alive connection right after relaying the response to the
    real client), call_next() can raise instead of returning, silently
    skipping any code written after it. Logging inside this middleware's own
    try/finally around the direct app call cannot be skipped that way.

    Registered as the outermost middleware so `total` covers every other
    middleware, dependency (auth, tenant scoping), and the route handler --
    not just the route body.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        token = _query_durations_ms.set([])
        start = time.perf_counter()
        try:
            await self.app(scope, receive, send)
        finally:
            durations = _query_durations_ms.get() or []
            _query_durations_ms.reset(token)
            total_ms = (time.perf_counter() - start) * 1000
            db_ms = sum(durations)
            logger.info(
                "%s %s total=%.1fms db=%.1fms(%dq) other=%.1fms",
                scope["method"],
                scope["path"],
                total_ms,
                db_ms,
                len(durations),
                total_ms - db_ms,
            )
