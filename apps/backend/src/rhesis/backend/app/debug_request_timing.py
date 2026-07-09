"""Temporary request-vs-DB timing probe for diagnosing the /tests latency gap.

Per-query timing already includes network round-trip time, since
cursor.execute() blocks until Postgres responds. It does NOT explain time
spent outside DB calls entirely -- ORM row hydration, connection-pool
checkout wait, and per-request auth/dependency overhead (e.g.
require_permission's authorize() check). This module measures both: the
aggregate total-vs-db split, AND a per-query breakdown (normalized SQL +
duration, slowest first) so a single log line can point at exactly which
query dominates a slow request, not just that "db was slow".

Enable with RHESIS_ENABLE_REQUEST_TIMING=1. Logs one summary line plus one
line per query for each request:

    GET /tests/?skip=75&limit=25 total=2190.3ms db=1181.4ms(17q) other=1008.9ms
      412.1ms | SELECT test.id FROM test JOIN behavior ON ... WHERE ...
      203.4ms | SELECT prompt.id, prompt.content FROM prompt WHERE prompt.id IN (?)
      ...

Not meant to run in production long-term -- remove once the gap is
diagnosed, same as the earlier debug_sql_timing.py probe (commit
57ed58154, reverted in 639a09d3c).
"""

import logging
import os
import re
import sys
import time
from contextvars import ContextVar

from sqlalchemy import event

from rhesis.backend.app.database import engine

logger = logging.getLogger("request_timing")
logger.setLevel(logging.INFO)
logger.propagate = False
# Don't rely on the root logger's handlers -- in this environment
# (is_google_cloud=False, backend_env != "local") set_logger() clears root's
# handlers and adds nothing back, so anything that propagates to root ends up
# wherever some other library's logging setup happens to redirect it (e.g.
# garak's own FileHandler) instead of stdout. Attach our own handler so this
# probe's output is visible regardless of that gap.
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(message)s"))
    logger.addHandler(_handler)

# Each entry: (elapsed_ms, normalized_sql)
_query_log: ContextVar[list | None] = ContextVar("_query_log", default=None)


def is_enabled() -> bool:
    return os.environ.get("RHESIS_ENABLE_REQUEST_TIMING", "").lower() in ("1", "true")


def _normalize(statement: str) -> str:
    """Collapse literal placeholders and whitespace so the line stays readable."""
    normalized = re.sub(r"%\([a-zA-Z_0-9]+\)s", "?", statement)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized[:200]


@event.listens_for(engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("_query_start_times", []).append(time.perf_counter())


@event.listens_for(engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    start_times = conn.info.get("_query_start_times")
    if not start_times:
        return
    elapsed_ms = (time.perf_counter() - start_times.pop()) * 1000
    log = _query_log.get()
    if log is not None:
        log.append((elapsed_ms, _normalize(statement)))


class RequestTimingMiddleware:
    """Logs total/db/other wall-clock time plus a per-query breakdown.

    Plain ASGI middleware rather than BaseHTTPMiddleware -- the latter runs
    the downstream app via call_next() in a background task, and if the
    server-side connection gets cancelled (observed behind nginx-ingress
    connection reuse, not reproducible via direct port-forward) call_next()
    raises instead of returning, silently skipping any code written after
    it. Logging inside this middleware's own try/finally around the direct
    app call cannot be skipped that way.

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

        token = _query_log.set([])
        start = time.perf_counter()
        try:
            await self.app(scope, receive, send)
        finally:
            log = _query_log.get() or []
            _query_log.reset(token)
            total_ms = (time.perf_counter() - start) * 1000
            db_ms = sum(elapsed for elapsed, _ in log)
            query_string = scope.get("query_string", b"").decode()
            path = scope["path"] + (f"?{query_string}" if query_string else "")
            logger.info(
                "%s %s total=%.1fms db=%.1fms(%dq) other=%.1fms",
                scope["method"],
                path,
                total_ms,
                db_ms,
                len(log),
                total_ms - db_ms,
            )
            for elapsed_ms, sql in sorted(log, reverse=True):
                logger.info("  %.1fms | %s", elapsed_ms, sql)
