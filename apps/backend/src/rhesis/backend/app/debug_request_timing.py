"""Temporary request-vs-DB timing probe for diagnosing the /tests latency gap.

Per-query timing already includes network round-trip time, since
cursor.execute() blocks until Postgres responds. It does NOT explain time
spent outside DB calls entirely -- ORM row hydration, connection-pool
checkout wait, and per-request auth/dependency overhead (e.g.
require_permission's authorize() check). This module measures both: the
aggregate total-vs-db split, AND a per-query breakdown (normalized SQL +
duration, slowest first) so a single log line can point at exactly which
query dominates a slow request, not just that "db was slow".

"other" (total - db) is itself a grab bag, so three more phases are broken
out of it:

- ``pre_db``: wall-clock from request start to the first DB cursor execute.
  A proxy for connection-pool checkout wait + dependency resolution (tenant
  scoping, auth) that happens before any query runs -- there's no public
  SQLAlchemy "about to wait for a pool slot" hook, so this is measured
  indirectly instead of instrumenting the pool.
- ``authz``: time inside ``rbac.authorize()``, the single authorization
  decision point (cache lookup + provider call). Patched onto the live
  function object at import time rather than instrumented in rbac.py itself,
  so this probe stays fully confined to this file and costs nothing when
  RHESIS_ENABLE_REQUEST_TIMING is unset.
- ``encode``: wall-clock from the first ASGI ``http.response.start`` message
  to the last message sent. Covers response-model serialization (incl. the
  ``permitted_actions`` affordance validator), JSON encoding, and gzip --
  everything that happens after the route handler has produced its return
  value. ``handler`` (total minus encode) is what's left: dependencies +
  route body + DB work.

Enable with RHESIS_ENABLE_REQUEST_TIMING=1. Logs one summary line plus one
line per query for each request:

    GET /tests/?skip=75&limit=25 total=2190.3ms db=1181.4ms(17q) \
pre_db=45.2ms authz=8.1ms handler=1980.9ms encode=209.4ms other=1008.9ms
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
# Named sub-phases (e.g. "authz") accumulated per request; see module docstring.
_phase_log: ContextVar[dict | None] = ContextVar("_phase_log", default=None)
# Wall-clock time.perf_counter() the current request started, for the pre_db proxy.
_request_start: ContextVar[float | None] = ContextVar("_request_start", default=None)


def is_enabled() -> bool:
    return os.environ.get("RHESIS_ENABLE_REQUEST_TIMING", "").lower() in ("1", "true")


def _record_phase(name: str, elapsed_ms: float) -> None:
    log = _phase_log.get()
    if log is not None:
        log[name] = log.get(name, 0.0) + elapsed_ms


def _normalize(statement: str) -> str:
    """Collapse literal placeholders and whitespace so the line stays readable."""
    normalized = re.sub(r"%\([a-zA-Z_0-9]+\)s", "?", statement)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized[:200]


@event.listens_for(engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("_query_start_times", []).append(time.perf_counter())
    log = _query_log.get()
    request_start = _request_start.get()
    if log is not None and not log and request_start is not None:
        _record_phase("pre_db", (time.perf_counter() - request_start) * 1000)


@event.listens_for(engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    start_times = conn.info.get("_query_start_times")
    if not start_times:
        return
    elapsed_ms = (time.perf_counter() - start_times.pop()) * 1000
    log = _query_log.get()
    if log is not None:
        log.append((elapsed_ms, _normalize(statement)))


def _patch_authorize() -> None:
    """Wrap ``rbac.authorize`` in place to time the authz decision point.

    ``require_permission``'s inner dependency calls ``authorize(...)`` as a
    bare module-global lookup, so reassigning ``rbac.authorize`` here is
    picked up without touching rbac.py. Routers that imported ``authorize``
    directly (`from ...rbac import authorize`) keep their own bound
    reference and won't be timed -- acceptable for a diagnostic probe, since
    the backstop-injected `require_permission` dependency is the dominant path.
    """
    from rhesis.backend.app.auth import rbac

    if getattr(rbac.authorize, "_rhesis_timing_patched", False):
        return

    original = rbac.authorize

    def _timed_authorize(*args, **kwargs):
        start = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            _record_phase("authz", (time.perf_counter() - start) * 1000)

    _timed_authorize._rhesis_timing_patched = True
    rbac.authorize = _timed_authorize


if is_enabled():
    _patch_authorize()


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

        query_token = _query_log.set([])
        phase_token = _phase_log.set({})
        start = time.perf_counter()
        start_token = _request_start.set(start)

        # Marks when the route handler finished and Starlette began sending
        # the response, splitting `handler` (deps + route body + DB) from
        # `encode` (serialization, incl. the affordance validator, + gzip).
        first_send_time = None

        async def _timed_send(message):
            nonlocal first_send_time
            if first_send_time is None and message.get("type") == "http.response.start":
                first_send_time = time.perf_counter()
            await send(message)

        try:
            await self.app(scope, receive, _timed_send)
        finally:
            log = _query_log.get() or []
            phases = _phase_log.get() or {}
            _query_log.reset(query_token)
            _phase_log.reset(phase_token)
            _request_start.reset(start_token)

            end = time.perf_counter()
            total_ms = (end - start) * 1000
            db_ms = sum(elapsed for elapsed, _ in log)
            handler_ms = ((first_send_time - start) * 1000) if first_send_time else total_ms
            encode_ms = max(total_ms - handler_ms, 0.0)

            query_string = scope.get("query_string", b"").decode()
            path = scope["path"] + (f"?{query_string}" if query_string else "")
            logger.info(
                "%s %s total=%.1fms db=%.1fms(%dq) pre_db=%.1fms authz=%.1fms "
                "handler=%.1fms encode=%.1fms other=%.1fms",
                scope["method"],
                path,
                total_ms,
                db_ms,
                len(log),
                phases.get("pre_db", 0.0),
                phases.get("authz", 0.0),
                handler_ms,
                encode_ms,
                total_ms - db_ms,
            )
            for elapsed_ms, sql in sorted(log, reverse=True):
                logger.info("  %.1fms | %s", elapsed_ms, sql)
