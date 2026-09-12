"""Guard: a coroutine route handler must never be handed a synchronous Session.

FastAPI runs ``async def`` handlers and dependencies on the event loop. A
SQLAlchemy ``Session`` there means every psycopg2 call blocks the loop, and one
slow query stalls every other request, WebSocket frame and ``/health`` probe in
the worker process. ``def`` handlers run in the anyio threadpool, where the
same call only blocks its own thread.

For every ``APIRoute`` whose endpoint is a coroutine function this test walks
the dependant tree and fails if a Session reaches any coroutine in it. Only
coroutine dependencies are descended into: a Session yielded to a *sync*
dependency runs in the threadpool and is fine.

A handler that genuinely has to be ``async`` (streams a response, awaits
external HTTP, ``asyncio.gather``) declares ``db: OffLoopSession =
Depends(get_off_loop_tenant_session)`` and does every session operation inside
``await anyio.to_thread.run_sync(...)``. The ``NewType`` is what makes this test
skip it; see ``dependencies.get_off_loop_tenant_session`` for what that
annotation promises and why only review can check it.
"""

import inspect
import typing

import pytest
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from rhesis.backend.app.dependencies import (
    bind_affordance_context,
    get_db_session,
    get_db_with_tenant_context,
    get_tenant_db_session,
)

#: Dependencies that yield a sync ``Session``.
SESSION_DEPENDENCIES = frozenset(
    {get_tenant_db_session, get_db_session, get_db_with_tenant_context}
)

#: Coroutine dependencies that are handed a Session but only use it inside
#: ``anyio.to_thread.run_sync``. ``bind_affordance_context`` must be async so
#: the ContextVar it sets is visible during response serialization; its
#: ``precompute()`` runs in the threadpool (see tests/backend/auth/test_affordance_context.py).
OFF_LOOP_COROUTINE_DEPENDENCIES = frozenset({bind_affordance_context})

#: "METHOD path" routes still holding a Session in a coroutine handler.
#:
#: Every one of these hands ``db`` to a coroutine it awaits, so the handler
#: cannot be fixed on its own -- the awaited service has to stop taking a
#: session (or take the work off the loop itself) first. The function that has
#: to change is named against each group.
#:
#: This list only shrinks. Adding to it is a regression: make the handler
#: ``def``, or keep it async and move the DB work off the loop.
ALLOWED_OFFENDERS: frozenset[str] = frozenset(
    {
        # services/test_execution.py hands ``db`` to SingleTurnRunner.run /
        # MultiTurnRunner.run (jobs/execution/executors/runners.py), which query
        # between their awaits: get_test_metrics, _get_endpoint_routing,
        # MetricEvaluator + evaluate_*_metrics (which runs the judge LLM calls
        # synchronously, so the loop is held for the whole evaluation),
        # _signal_penelope_conversation_complete, and SingleTurnOutput.get_output.
        # Clearing it means wrapping those six call sites in run_sync inside
        # runners.py, which the Celery executors share, and is a change of its own.
        "POST /tests/execute",
    }
)


def _is_coroutine(call) -> bool:
    return inspect.iscoroutinefunction(call) or inspect.isasyncgenfunction(call)


def _takes_session(call) -> bool:
    """True if ``call`` annotates any parameter as a SQLAlchemy Session."""
    try:
        hints = typing.get_type_hints(call)
    except Exception:
        hints = {}
    try:
        params = inspect.signature(call).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(hints.get(p.name, p.annotation) is Session for p in params)


def _coroutine_holds_session(dependant, seen: set[int]) -> bool:
    """True if this coroutine dependant, or a coroutine below it, is handed a Session."""
    if _takes_session(dependant.call):
        return True
    for sub in dependant.dependencies:
        call = sub.call
        if call is None or id(call) in seen:
            continue
        seen.add(id(call))
        if call in SESSION_DEPENDENCIES:
            return True
        if call in OFF_LOOP_COROUTINE_DEPENDENCIES or not _is_coroutine(call):
            continue
        if _coroutine_holds_session(sub, seen):
            return True
    return False


def _offending_routes(app) -> set[str]:
    offenders: set[str] = set()
    for route in app.router.routes:
        if not isinstance(route, APIRoute) or not _is_coroutine(route.endpoint):
            continue
        if _coroutine_holds_session(route.dependant, seen=set()):
            offenders.update(f"{m} {route.path}" for m in route.methods)
    return offenders


@pytest.mark.unit
class TestNoSyncSessionOnEventLoop:
    def test_coroutine_handlers_hold_no_session(self):
        from rhesis.backend.app.main import app

        offenders = _offending_routes(app)
        new = sorted(offenders - ALLOWED_OFFENDERS)
        assert not new, (
            "These coroutine route handlers are handed a sync Session, which runs the "
            "database call on the event loop. Make the handler `def`, or keep it async "
            "and move the DB work into `await anyio.to_thread.run_sync(...)`:\n  "
            + "\n  ".join(new)
        )

    def test_allowlist_has_not_rotted(self):
        """An allowlisted route that no longer offends must be removed from the list."""
        from rhesis.backend.app.main import app

        offenders = _offending_routes(app)
        stale = sorted(ALLOWED_OFFENDERS - offenders)
        assert not stale, (
            "These routes are in ALLOWED_OFFENDERS but no longer hold a Session in a "
            "coroutine handler; drop them from the list:\n  " + "\n  ".join(stale)
        )
