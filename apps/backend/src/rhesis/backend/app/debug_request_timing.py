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
- ``pool_checkout`` (with a ``(Nnew)`` count): time inside ``Engine.connect()``,
  the call a ``Session`` makes to pull a connection out of the pool -- a
  direct measurement, not a proxy, since that call blocks for real if the
  pool has to make the caller wait. Near-zero when an idle connection is
  ready. The ``(Nnew)`` count is from the SQLAlchemy ``connect`` pool event,
  which only fires when a *brand-new* physical connection is opened (TCP +
  TLS + Postgres auth) rather than an existing one being handed out -- there's
  no matching "about to open" event, so this is a count, not its own
  duration. If ``pool_checkout`` is large and ``new`` is 0, that time was
  pure queue-wait for an already-open connection; if ``new`` > 0, some of it
  was connection setup. Real request evidence (2026-07-13, ``/tests/`` page)
  showed the ``SET app.current_organization/...`` GUC line repeating 8 times
  in one request -- each repeat means a checkout, since those GUCs are
  transaction-scoped and get re-applied per checkout.
- ``orm_execute``: time inside ``Session.execute()``, the ORM-level call
  underneath ``Query.all()``/relationship loaders in SQLAlchemy 2.0 (legacy
  ``Query`` is implemented on top of it). Covers statement compilation +
  the DBAPI round-trip + however much row-to-object materialization happens
  before the call returns. ``orm_execute - db`` (``orm_nondb``) is a more
  direct estimate of ORM hydration cost than ``endpoint_nondb``, though not
  exact: some materialization can happen lazily on result iteration *after*
  ``execute()`` returns, so this may still undercount hydration.
- ``pre_query`` / ``between_query`` / ``post_query``: an exact partition of
  ``endpoint_nondb`` using the start/end timestamp of every query plus the
  ``run_endpoint_function`` span (see ``_gap_breakdown``), not a further
  guess. ``pre_query`` is route-body work before the first query fires
  (building filters/pagination); ``between_query`` is cumulative gaps
  between one query finishing and the next starting (processing one query's
  rows to build the next -- e.g. an ID list feeding a second query -- or ORM
  bookkeeping between round-trips); ``post_query`` is work after the last
  query returns but before the route function itself returns (final
  assembly/hydration not yet claimed by ``validate``/``to_json``).
  ``pre_query + between_query + post_query`` sums to ``endpoint_nondb``.

``deps + endpoint + validate + to_json`` should roughly equal ``handler``
minus a small residual (FastAPI's own glue code) -- large unexplained gaps
there point at something this probe still isn't instrumenting.

Five more signals, each testing a specific hypothesis rather than measuring
a FastAPI/SQLAlchemy internal stage directly:

- ``compile``: gap between ``before_execute`` (fires before a statement is
  compiled to SQL) and ``before_cursor_execute`` (fires after, right before
  the DBAPI call) for the same statement. SQLAlchemy caches compiled
  statements, so this should be small on a cache hit and larger the first
  time a given query shape runs; consistently large values across requests
  would mean the cache isn't being hit.
- ``threadpool`` (``borrowed/total``): a snapshot of anyio's default worker
  thread pool -- ``borrowed`` other threads in use, ``total`` the pool size
  -- taken the instant ``run_endpoint_function`` starts, before it tries to
  acquire a thread for a sync route. If ``borrowed`` is at or near ``total``
  on a slow request, the route was queued waiting for a free worker thread
  before any of its own code ran -- a symptom of concurrent load, not
  anything wrong with this request's own logic.
- ``inflight``: how many other requests this process was already handling
  when this one started (a simple in-process counter, incremented/decremented
  around the whole middleware span). Lets you correlate a slow request with
  "the pod was just busy" rather than treating every slow sample as
  independently mysterious.
- ``gc``: cumulative time inside CPython's garbage collector (``gc.callbacks``)
  while this request was in flight. Attributed to whichever request's
  context happened to be active when a collection ran -- a rough attribution
  under concurrency (GC pauses are process-wide, not per-request), but a
  clean signal if the pause is caused by *this* request allocating a lot of
  short-lived objects (e.g. building a wide ORM/Pydantic object graph).
- ``gzip``: NOT instrumented, noted here as a known gap. ``GZipMiddleware``
  sits between this probe (outermost) and the route, so if it buffers and
  compresses the whole body before emitting the first ASGI message, that
  time is currently invisible -- it doesn't land in ``encode`` (which only
  sees post-compression bytes) and isn't claimed by ``deps``/``endpoint``
  either. If ``unlabeled`` is ever large, this is the next thing to
  instrument, by timing ``GZipResponder`` specifically rather than guessing.

Enable with RHESIS_ENABLE_REQUEST_TIMING=1. Logs one summary line plus one
line per query for each request:

    GET /tests/?skip=75&limit=25 total=2190.3ms db=1181.4ms(17q) \
pre_db=45.2ms pool_checkout=3.1ms(1new) deps=52.1ms authz=8.1ms \
endpoint=1820.4ms endpoint_nondb=639.0ms pre_query=12.0ms between_query=430.1ms \
post_query=196.9ms orm_execute=1350.9ms orm_nondb=169.5ms compile=22.4ms \
threadpool=3/40 inflight=2 gc=8.1ms validate=140.2ms affordance=0.0ms \
to_json=25.6ms handler=2038.3ms encode=152.0ms unlabeled=13.4ms
      412.1ms | SELECT test.id FROM test JOIN behavior ON ... WHERE ...
      203.4ms | SELECT prompt.id, prompt.content FROM prompt WHERE prompt.id IN (?)
      ...

Not meant to run in production long-term -- remove once the gap is
diagnosed, same as the earlier debug_sql_timing.py probe (commit
57ed58154, reverted in 639a09d3c).
"""

import gc
import logging
import os
import re
import sys
import threading
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

# Each entry: (start_ts, end_ts, elapsed_ms, normalized_sql) -- start/end are
# time.perf_counter() values, kept so the middleware can compute gaps between
# queries (see _gap_breakdown), not just their own durations.
_query_log: ContextVar[list | None] = ContextVar("_query_log", default=None)
# Named sub-phases (e.g. "authz") accumulated per request; see module docstring.
_phase_log: ContextVar[dict | None] = ContextVar("_phase_log", default=None)
# Wall-clock time.perf_counter() the current request started, for the pre_db proxy.
_request_start: ContextVar[float | None] = ContextVar("_request_start", default=None)
# List of (start_ts, end_ts) spans, one per run_endpoint_function() call (normally
# just one), for the gap breakdown.
_endpoint_span: ContextVar[list | None] = ContextVar("_endpoint_span", default=None)

# Process-wide count of requests currently in flight (not per-request -- read at
# request start to see how busy the pod already was). Diagnostic-only: a plain
# int guarded by a lock is fine, no need for anything fancier here.
_inflight_lock = threading.Lock()
_inflight_count = 0


def is_enabled() -> bool:
    return os.environ.get("RHESIS_ENABLE_REQUEST_TIMING", "").lower() in ("1", "true")


def _record_phase(name: str, elapsed_ms: float) -> None:
    log = _phase_log.get()
    if log is not None:
        log[name] = log.get(name, 0.0) + elapsed_ms


def _record_gauge(name: str, value: float) -> None:
    """Like ``_record_phase`` but overwrites instead of summing -- for
    point-in-time snapshots (e.g. thread-pool occupancy) rather than durations
    that should accumulate across multiple calls in one request.
    """
    log = _phase_log.get()
    if log is not None:
        log[name] = value


def _normalize(statement: str) -> str:
    """Collapse literal placeholders and whitespace so the line stays readable."""
    normalized = re.sub(r"%\([a-zA-Z_0-9]+\)s", "?", statement)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized[:200]


@event.listens_for(engine, "before_execute")
def _before_execute(conn, clauseelement, multiparams, params, execution_options):
    """Fires before a statement is compiled to SQL -- pairs with
    before_cursor_execute (fires after compilation, right before the DBAPI
    call) to time compilation via the gap between them. See ``compile`` in the
    module docstring.
    """
    conn.info.setdefault("_execute_start_times", []).append(time.perf_counter())


@event.listens_for(engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    now = time.perf_counter()
    conn.info.setdefault("_query_start_times", []).append(now)
    execute_start_times = conn.info.get("_execute_start_times")
    if execute_start_times:
        _record_phase("compile", (now - execute_start_times.pop()) * 1000)
    log = _query_log.get()
    request_start = _request_start.get()
    if log is not None and not log and request_start is not None:
        _record_phase("pre_db", (now - request_start) * 1000)


@event.listens_for(engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    start_times = conn.info.get("_query_start_times")
    if not start_times:
        return
    start_ts = start_times.pop()
    end_ts = time.perf_counter()
    log = _query_log.get()
    if log is not None:
        log.append((start_ts, end_ts, (end_ts - start_ts) * 1000, _normalize(statement)))


@event.listens_for(engine, "connect")
def _on_new_connection(dbapi_connection, connection_record):
    """Fires only when the pool opens a brand-new physical connection (TCP +
    TLS + Postgres auth) -- as opposed to handing out an already-open one.
    A count, not a duration: there's no matching "about to open" event to
    pair it with, so this can't be timed directly, only counted. If
    ``pool_checkout`` is large and this count is 0 for the request, the
    time was queue-wait, not connection setup.
    """
    _record_phase("new_connections", 1)


# Not request-scoped: gc.callbacks fires for every collection in the process,
# regardless of which request (if any) triggered it. A plain module-level
# holder is fine here -- CPython's cyclic GC isn't reentrant, so "start" and
# "stop" always alternate on a single collection at a time.
_gc_collection_start: float | None = None


def _gc_callback(phase, info) -> None:
    """Times each garbage-collection pause and attributes it to whichever
    request's context is active when it happens -- see ``gc`` in the module
    docstring for why this is an approximation, not an exact per-request cost.
    """
    global _gc_collection_start
    if phase == "start":
        _gc_collection_start = time.perf_counter()
    elif phase == "stop" and _gc_collection_start is not None:
        _record_phase("gc", (time.perf_counter() - _gc_collection_start) * 1000)
        _gc_collection_start = None


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
        # Snapshot before the sync route tries to acquire a worker thread --
        # see `threadpool` in the module docstring. anyio only exposes this
        # inside a running event loop, which this coroutine always is.
        try:
            import anyio.to_thread

            limiter = anyio.to_thread.current_default_thread_limiter()
            _record_gauge("threadpool_borrowed", limiter.borrowed_tokens)
            _record_gauge("threadpool_total", limiter.total_tokens)
        except Exception:
            pass

        start = time.perf_counter()
        try:
            return await original_run_endpoint_function(*args, **kwargs)
        finally:
            end = time.perf_counter()
            _record_phase("endpoint", (end - start) * 1000)
            span_holder = _endpoint_span.get()
            if span_holder is not None:
                span_holder.append((start, end))

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


def _patch_engine_connect() -> None:
    """Time ``Engine.connect()`` -- the call that pulls a connection out of the pool.

    Public, stable API (unlike ``Pool``'s internal queueing), so this is a
    direct measurement of checkout wait rather than a proxy: near-zero when a
    connection is immediately available, larger if the request has to wait
    for the pool to free one up.
    """
    from sqlalchemy.engine import Engine

    if getattr(Engine.connect, "_rhesis_timing_patched", False):
        return

    original_connect = Engine.connect

    def _timed_connect(self, *args, **kwargs):
        start = time.perf_counter()
        try:
            return original_connect(self, *args, **kwargs)
        finally:
            _record_phase("pool_checkout", (time.perf_counter() - start) * 1000)

    _timed_connect._rhesis_timing_patched = True
    Engine.connect = _timed_connect


def _patch_session_execute() -> None:
    """Time ``Session.execute()`` -- the ORM-level call underneath ``Query.all()``
    and relationship loaders, covering compile + DBAPI round-trip + whatever
    row materialization happens before it returns. See module docstring for
    why ``orm_execute - db`` is a better (though not exact) hydration estimate
    than ``endpoint - db``.
    """
    from sqlalchemy.orm import Session

    if getattr(Session.execute, "_rhesis_timing_patched", False):
        return

    original_execute = Session.execute

    def _timed_execute(self, *args, **kwargs):
        start = time.perf_counter()
        try:
            return original_execute(self, *args, **kwargs)
        finally:
            _record_phase("orm_execute", (time.perf_counter() - start) * 1000)

    _timed_execute._rhesis_timing_patched = True
    Session.execute = _timed_execute


if is_enabled():
    _patch_authorize()
    _patch_permitted_actions_for()
    _patch_fastapi_request_stages()
    _patch_engine_connect()
    _patch_session_execute()
    if _gc_callback not in gc.callbacks:
        gc.callbacks.append(_gc_callback)


def _gap_breakdown(query_log: list, endpoint_span: "tuple | None") -> tuple[float, float, float]:
    """Partition endpoint_nondb into pre/between/post-query Python time.

    Given the (start_ts, end_ts, ...) of every query and the
    (start_ts, end_ts) of the run_endpoint_function() call that contained
    them, returns (pre_query_ms, between_query_ms, post_query_ms):

    - pre_query_ms: route body work before the first query fires (building
      filters, resolving pagination params, etc).
    - between_query_ms: cumulative gaps between one query finishing and the
      next starting -- Python processing one query's rows to build the next
      (e.g. an ID list feeding a second query), or ORM bookkeeping between
      round-trips.
    - post_query_ms: route body work after the last query returns, before
      run_endpoint_function itself returns (final assembly, list-building,
      anything not yet claimed by the validate/to_json serialization phases).

    Queries outside the endpoint span (e.g. the tenant-scoping SET_CONFIG
    that runs during dependency resolution) are excluded -- they belong to
    ``deps``, not ``endpoint``.
    """
    if not endpoint_span:
        return (0.0, 0.0, 0.0)
    ep_start, ep_end = endpoint_span[0]
    in_span = sorted(
        (q for q in query_log if ep_start <= q[0] <= ep_end),
        key=lambda q: q[0],
    )
    if not in_span:
        return (max((ep_end - ep_start) * 1000, 0.0), 0.0, 0.0)

    pre_query_ms = max((in_span[0][0] - ep_start) * 1000, 0.0)
    post_query_ms = max((ep_end - in_span[-1][1]) * 1000, 0.0)
    between_query_ms = sum(
        max((in_span[i + 1][0] - in_span[i][1]) * 1000, 0.0) for i in range(len(in_span) - 1)
    )
    return (pre_query_ms, between_query_ms, post_query_ms)


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
        span_token = _endpoint_span.set([])
        start = time.perf_counter()
        start_token = _request_start.set(start)

        global _inflight_count
        with _inflight_lock:
            inflight_at_start = _inflight_count
            _inflight_count += 1

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
            spans = _endpoint_span.get() or []
            _query_log.reset(query_token)
            _phase_log.reset(phase_token)
            _endpoint_span.reset(span_token)
            _request_start.reset(start_token)
            with _inflight_lock:
                _inflight_count -= 1

            end = time.perf_counter()
            total_ms = (end - start) * 1000
            db_ms = sum(elapsed_ms for _, _, elapsed_ms, _ in log)
            handler_ms = ((first_send_time - start) * 1000) if first_send_time else total_ms
            encode_ms = max(total_ms - handler_ms, 0.0)

            deps_ms = phases.get("deps", 0.0)
            endpoint_ms = phases.get("endpoint", 0.0)
            validate_ms = phases.get("validate", 0.0)
            to_json_ms = phases.get("to_json", 0.0)
            pool_checkout_ms = phases.get("pool_checkout", 0.0)
            orm_execute_ms = phases.get("orm_execute", 0.0)
            new_connections = int(phases.get("new_connections", 0.0))
            compile_ms = phases.get("compile", 0.0)
            gc_ms = phases.get("gc", 0.0)
            threadpool_borrowed = int(phases.get("threadpool_borrowed", 0.0))
            threadpool_total = int(phases.get("threadpool_total", 0.0))
            # Everything endpoint() spent that wasn't a DB cursor.execute() --
            # ORM row hydration + pure-Python route logic, previously invisible.
            endpoint_nondb_ms = max(endpoint_ms - db_ms, 0.0)
            # A tighter hydration estimate than endpoint_nondb: Session.execute()
            # wraps compile + cursor round-trip + (some) materialization, so this
            # is closer to "hydration only" -- see module docstring for caveats.
            orm_nondb_ms = max(orm_execute_ms - db_ms, 0.0)
            # Precise partition of endpoint_nondb into before/between/after the
            # route's own DB queries -- see _gap_breakdown docstring.
            pre_query_ms, between_query_ms, post_query_ms = _gap_breakdown(log, spans)
            # Should be small: what's left of `handler` once every instrumented
            # FastAPI stage is subtracted out. Large here means something is
            # still unaccounted for.
            unlabeled_ms = max(handler_ms - deps_ms - endpoint_ms - validate_ms - to_json_ms, 0.0)

            query_string = scope.get("query_string", b"").decode()
            path = scope["path"] + (f"?{query_string}" if query_string else "")
            logger.info(
                "%s %s total=%.1fms db=%.1fms(%dq) pre_db=%.1fms "
                "pool_checkout=%.1fms(%dnew) deps=%.1fms authz=%.1fms "
                "endpoint=%.1fms endpoint_nondb=%.1fms pre_query=%.1fms "
                "between_query=%.1fms post_query=%.1fms orm_execute=%.1fms "
                "orm_nondb=%.1fms compile=%.1fms threadpool=%d/%d inflight=%d gc=%.1fms "
                "validate=%.1fms affordance=%.1fms to_json=%.1fms handler=%.1fms "
                "encode=%.1fms unlabeled=%.1fms",
                scope["method"],
                path,
                total_ms,
                db_ms,
                len(log),
                phases.get("pre_db", 0.0),
                pool_checkout_ms,
                new_connections,
                deps_ms,
                phases.get("authz", 0.0),
                endpoint_ms,
                endpoint_nondb_ms,
                pre_query_ms,
                between_query_ms,
                post_query_ms,
                orm_execute_ms,
                orm_nondb_ms,
                compile_ms,
                threadpool_borrowed,
                threadpool_total,
                inflight_at_start,
                gc_ms,
                validate_ms,
                phases.get("affordance", 0.0),
                to_json_ms,
                handler_ms,
                encode_ms,
                unlabeled_ms,
            )
            for _, _, elapsed_ms, sql in sorted(log, key=lambda q: q[2], reverse=True):
                logger.info("  %.1fms | %s", elapsed_ms, sql)
