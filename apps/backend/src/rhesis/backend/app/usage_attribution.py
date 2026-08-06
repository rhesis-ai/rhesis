"""Ambient organization context for token-usage accrual.

Answers one question at the moment an LLM reports token usage: *which
organization pays for this?* It is deliberately separate from
``app.scope.RequestScope``, which answers a different question (which rows
may this session touch) and is bound to a DB session rather than to the
running task.

Why ambient at all. Accrual used to work by closing over an organization id
at model-construction time and passing the resulting callback into every
model constructor. That made attribution a thing each call site had to
remember, and call sites forgot -- three times before this module existed,
each one found only because someone went looking. Reading the org at
*emission* time instead means a new code path cannot silently skip accrual:
there is nothing to wire.

Bound in the two places that already establish tenant context:

- FastAPI, via ``_bind_usage_attribution`` in ``app.dependencies``. It must
  be an ``async def`` dependency. A sync dependency runs in the anyio
  threadpool, and a ContextVar set in a child thread is invisible to the
  request's own task -- which is exactly why ``app.scope``'s ContextVar is
  documented as unusable from request handlers. An async dependency runs in
  the request task itself and does not have that problem.
- Celery, via the ``task_prerun``/``task_postrun`` handlers in
  ``celery.signals``.

Propagation, by boundary:

===========================================  ==========================
``asyncio.to_thread`` / ``anyio.to_thread``  carries (stdlib copies it)
``asyncio.create_task`` / ``gather``         carries
``ThreadPoolExecutor.submit``                **does not** -- wrap with
``loop.run_in_executor``                     :func:`with_usage_attribution`
Celery ``.delay()``                          does not (separate process;
                                             rebound by ``task_prerun``)
===========================================  ==========================
"""

from __future__ import annotations

import contextvars
import functools
import logging
from contextlib import contextmanager
from typing import Callable, Iterator, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

_usage_org: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "usage_attribution_org", default=None
)


def current_usage_org() -> Optional[str]:
    """Organization to bill for usage emitted right now, if any is bound."""
    return _usage_org.get()


#: Results of ``str()`` on a null org id. Rejected rather than bound, because
#: they are truthy strings that sail through every ``if organization_id:``
#: guard and only fail much later, when the accrual task tries to cast one to
#: a UUID. Review of #2355 caught exactly this shape reaching
#: ``dispatch_accrual`` via ``str(user.organization_id)`` for an orgless user.
_NULL_ORG_STRINGS = frozenset({"none", "null", "nil", "undefined", ""})


def bind_usage_org(organization_id: Optional[str]) -> contextvars.Token:
    """Bind *organization_id* for the current context; returns a reset token.

    Prefer :func:`usage_attribution` where a ``with`` block fits. This exists
    for the two framework hooks that bind and reset in separate callbacks
    (FastAPI dependency teardown, Celery ``task_postrun``).

    A stringified null binds as unattributed. Both real callers already guard
    against it; this makes the next one safe too, and unattributed usage is
    visible in the logs whereas a bogus org id is not.
    """
    if organization_id is not None and organization_id.strip().lower() in _NULL_ORG_STRINGS:
        logger.warning(
            "Ignoring stringified null organization id %r for usage attribution; "
            "the caller should pass None rather than str(None)",
            organization_id,
        )
        organization_id = None
    return _usage_org.set(organization_id or None)


def reset_usage_org(token: contextvars.Token) -> None:
    """Undo a :func:`bind_usage_org`, tolerating a token from another context.

    Celery reuses a worker process across tasks, so a leaked binding would
    quietly bill one org for another's tokens. A failed reset must therefore
    still leave the var unbound rather than propagating the error.
    """
    try:
        _usage_org.reset(token)
    except ValueError:
        # Token was created in a different Context (e.g. the task ran in a
        # thread the signal handler did not). Clearing outright is the safe
        # reading: better unattributed than attributed to the wrong org.
        _usage_org.set(None)


@contextmanager
def usage_attribution(organization_id: Optional[str]) -> Iterator[None]:
    """Attribute usage emitted inside the block to *organization_id*."""
    token = bind_usage_org(organization_id)
    try:
        yield
    finally:
        reset_usage_org(token)


def with_usage_attribution(fn: Callable[..., T]) -> Callable[..., T]:
    """Wrap *fn* so it runs with a copy of the caller's current context.

    For handing work to a ``ThreadPoolExecutor`` or ``run_in_executor``,
    neither of which copies context the way ``asyncio.to_thread`` does. The
    LLM-judge metric strategies and the Penelope target both fan out that
    way, so without this their token usage emits with no org bound.

    Copies the whole context, not just this module's var, so anything else
    ambient the caller had set survives the hop too.
    """
    ctx = contextvars.copy_context()

    @functools.wraps(fn)
    def _run(*args, **kwargs) -> T:
        return ctx.run(fn, *args, **kwargs)

    return _run
