"""Temporary request-vs-DB timing probe for diagnosing the /tests latency gap.

Per-query timing already includes network round-trip time, since
cursor.execute() blocks until Postgres responds. It does NOT explain time
spent outside DB calls entirely -- ORM row hydration, connection-pool
checkout wait, and per-request auth/dependency overhead (e.g.
require_permission's authorize() check). This module measures both: the
aggregate total-vs-db split, AND a per-query breakdown (normalized SQL +
duration, slowest first) so a single log line can point at exactly which
query dominates a slow request, not just that "db was slow".

A first cut split ``total`` into ``handler`` (everything up to the first
ASGI ``http.response.start`` message) and ``encode`` (everything after).
That was misleading: FastAPI does all response-model validation, the
``permitted_actions`` affordance validator, and JSON encoding *inside* the
route's ASGI callable, before it ever calls ``send()`` -- so all of that
landed in ``handler``, and ``encode`` measured almost nothing (just writing
already-built bytes to the socket). This version instruments FastAPI's own
internal request-handling stages directly instead of guessing from the
ASGI boundary:

- ``deps``: ``fastapi.routing.solve_dependencies`` -- resolving every
  ``Depends(...)`` in the route's dependency tree (auth, tenant DB session,
  permission checks). ``authz`` (time inside ``rbac.authorize()``) is a
  subset of this.
- ``endpoint``: ``fastapi.routing.run_endpoint_function`` -- the route
  body itself: building/running the DB query/queries and turning the
  result rows into ORM objects. ``db`` (subset of this) is only the
  ``cursor.execute()`` portion; ``endpoint - db`` is ORM row hydration plus
  any pure-Python logic in the route, previously invisible.
- ``validate`` / ``to_json``: the two halves of
  ``fastapi.routing.serialize_response``, patched at the
  ``ModelField.validate`` / ``ModelField.serialize`` / ``.serialize_json``
  level so both response *and* incidental request-param validation are
  covered. ``validate`` runs Pydantic model validation (attribute reads +
  any ``@model_validator``s, e.g. the affordance one) over every row in the
  response; ``to_json`` is pydantic-core's conversion to JSON-compatible
  output. ``affordance`` (subset of ``validate``) is time inside
  ``permitted_actions_for`` specifically, when the response model carries
  ``WithPermittedActions`` (``Test`` itself does not, so this is 0 for
  ``/tests/``).
- ``pre_db``: wall-clock from request start to the first DB cursor execute.
  A cruder proxy for connection-pool checkout wait that predates the
  ``deps`` instrumentation above -- kept as a cross-check since there's no
  public SQLAlchemy "about to wait for a pool slot" hook to measure pool
  wait directly.

``deps + endpoint + validate + to_json`` should roughly equal ``handler``
minus a small residual (FastAPI's own glue code) -- large unexplained gaps
there point at something this probe still isn't instrumenting.

Enable with RHESIS_ENABLE_REQUEST_TIMING=1. Logs one summary line plus one
line per query for each request:

    GET /tests/?skip=75&limit=25 total=2190.3ms db=1181.4ms(17q) \
pre_db=45.2ms deps=52.1ms authz=8.1ms endpoint=1820.4ms validate=140.2ms \
to_json=25.6ms affordance=0.0ms handler=2038.3ms encode=152.0ms
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


def _patch_permitted_actions_for() -> None:
    """Time ``permitted_actions_for``, the per-object affordance computation.

    Called from the ``WithPermittedActions`` model validator, which is the
    part of ``validate`` (below) this probe can't reach directly: pydantic-core
    compiles ``@model_validator``s into the class's core schema at class
    definition time, so patching the Python method afterwards would not be
    picked up. ``permitted_actions_for`` is a plain module function the
    validator calls into, and reassigning it here works the same way as the
    ``authorize`` patch above.
    """
    from rhesis.backend.app.auth import capabilities

    if getattr(capabilities.permitted_actions_for, "_rhesis_timing_patched", False):
        return

    original = capabilities.permitted_actions_for

    def _timed_permitted_actions_for(*args, **kwargs):
        start = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            _record_phase("affordance", (time.perf_counter() - start) * 1000)

    _timed_permitted_actions_for._rhesis_timing_patched = True
    capabilities.permitted_actions_for = _timed_permitted_actions_for

    # affordances.py imported the original function by reference
    # (`from ...capabilities import permitted_actions_for`), so its own module
    # global must be repointed too -- reassigning capabilities.permitted_actions_for
    # alone would not be visible there.
    from rhesis.backend.app.auth import affordances

    affordances.permitted_actions_for = _timed_permitted_actions_for


def _patch_fastapi_request_stages() -> None:
    """Time FastAPI's own per-request stages: deps, endpoint, validate, to_json.

    All three of ``solve_dependencies``, ``run_endpoint_function``, and
    ``serialize_response`` are free functions in ``fastapi.routing``, called by
    bare module-global name from the request-handling closure built once per
    route -- reassigning the module attribute here is picked up on every
    subsequent call, the same mechanism as the ``authorize`` patch above.

    ``serialize_response`` itself is not patched directly (its control flow
    -- sync vs threadpool validation, ``dump_json`` branch -- is internal and
    could drift across FastAPI versions); instead the two calls it makes
    (``field.validate`` and ``field.serialize``/``serialize_json``) are timed
    at the ``ModelField`` class level, which is stable regardless of how
    ``serialize_response`` invokes them. This also happens to cover query/path
    param validation, not just response serialization -- negligible next to a
    25-row response body, but not a pure "response serialization" number.
    """
    import fastapi.routing as fastapi_routing
    from fastapi._compat.v2 import ModelField

    if getattr(fastapi_routing.solve_dependencies, "_rhesis_timing_patched", False):
        return

    original_solve_dependencies = fastapi_routing.solve_dependencies
    original_run_endpoint_function = fastapi_routing.run_endpoint_function
    original_validate = ModelField.validate
    original_serialize = ModelField.serialize
    original_serialize_json = ModelField.serialize_json

    async def _timed_solve_dependencies(*args, **kwargs):
        start = time.perf_counter()
        try:
            return await original_solve_dependencies(*args, **kwargs)
        finally:
            _record_phase("deps", (time.perf_counter() - start) * 1000)

    async def _timed_run_endpoint_function(*args, **kwargs):
        start = time.perf_counter()
        try:
            return await original_run_endpoint_function(*args, **kwargs)
        finally:
            _record_phase("endpoint", (time.perf_counter() - start) * 1000)

    def _timed_validate(self, *args, **kwargs):
        start = time.perf_counter()
        try:
            return original_validate(self, *args, **kwargs)
        finally:
            _record_phase("validate", (time.perf_counter() - start) * 1000)

    def _timed_serialize(self, *args, **kwargs):
        start = time.perf_counter()
        try:
            return original_serialize(self, *args, **kwargs)
        finally:
            _record_phase("to_json", (time.perf_counter() - start) * 1000)

    def _timed_serialize_json(self, *args, **kwargs):
        start = time.perf_counter()
        try:
            return original_serialize_json(self, *args, **kwargs)
        finally:
            _record_phase("to_json", (time.perf_counter() - start) * 1000)

    _timed_solve_dependencies._rhesis_timing_patched = True
    fastapi_routing.solve_dependencies = _timed_solve_dependencies
    fastapi_routing.run_endpoint_function = _timed_run_endpoint_function
    ModelField.validate = _timed_validate
    ModelField.serialize = _timed_serialize
    ModelField.serialize_json = _timed_serialize_json


if is_enabled():
    _patch_authorize()
    _patch_permitted_actions_for()
    _patch_fastapi_request_stages()


class RequestTimingMiddleware:
    """Logs total/db/deps/endpoint/serialization time plus a per-query breakdown.

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

        # Marks when Starlette began sending the response. Kept for cross-checking
        # against deps+endpoint+validate+to_json below -- see module docstring for
        # why this boundary alone doesn't isolate serialization/gzip as `encode`
        # might suggest (both happen before the first send() call, i.e. inside
        # `handler`).
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

            deps_ms = phases.get("deps", 0.0)
            endpoint_ms = phases.get("endpoint", 0.0)
            validate_ms = phases.get("validate", 0.0)
            to_json_ms = phases.get("to_json", 0.0)
            # Everything endpoint() spent that wasn't a DB cursor.execute() --
            # ORM row hydration + pure-Python route logic, previously invisible.
            endpoint_nondb_ms = max(endpoint_ms - db_ms, 0.0)
            # Should be small: what's left of `handler` once every instrumented
            # FastAPI stage is subtracted out. Large here means something is
            # still unaccounted for.
            unlabeled_ms = max(handler_ms - deps_ms - endpoint_ms - validate_ms - to_json_ms, 0.0)

            query_string = scope.get("query_string", b"").decode()
            path = scope["path"] + (f"?{query_string}" if query_string else "")
            logger.info(
                "%s %s total=%.1fms db=%.1fms(%dq) pre_db=%.1fms deps=%.1fms "
                "authz=%.1fms endpoint=%.1fms endpoint_nondb=%.1fms validate=%.1fms "
                "affordance=%.1fms to_json=%.1fms handler=%.1fms encode=%.1fms "
                "unlabeled=%.1fms",
                scope["method"],
                path,
                total_ms,
                db_ms,
                len(log),
                phases.get("pre_db", 0.0),
                deps_ms,
                phases.get("authz", 0.0),
                endpoint_ms,
                endpoint_nondb_ms,
                validate_ms,
                phases.get("affordance", 0.0),
                to_json_ms,
                handler_ms,
                encode_ms,
                unlabeled_ms,
            )
            for elapsed_ms, sql in sorted(log, reverse=True):
                logger.info("  %.1fms | %s", elapsed_ms, sql)
