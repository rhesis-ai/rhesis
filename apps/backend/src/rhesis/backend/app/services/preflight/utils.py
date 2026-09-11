"""Preflight check utility functions."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Optional

import anyio
from sqlalchemy.orm import Session

from rhesis.backend.app.schemas.preflight import PreflightCheckResult, PreflightCheckStatus
from rhesis.backend.app.schemas.websocket import ChannelTarget, EventType, WebSocketMessage

from .constants import LABELS, PER_TEST_SET_CHECKS


class OffLoopDb:
    """The database access for one preflight run, kept off the event loop.

    Preflight fans its checks out with ``asyncio.gather``, and every check queries.
    Two rules have to hold at once: a psycopg2 call must not run on the event loop
    (it blocks every other request in the worker), and one ``Session`` must not be
    used from two threads at once. So each segment runs in a worker thread, under a
    lock that lets only one in at a time -- which serialises the queries exactly as
    the old on-loop code did, while the awaits around them still overlap.

    ``spawn_session`` is for the one branch that needs a session to stay open across
    an await: the endpoint invoker. Sharing the run's session there would either hold
    the lock for the whole probe or hand the same session to two tasks.
    """

    def __init__(
        self,
        session: Session,
        organization_id: str = "",
        user_id: str = "",
        project_id: str = "",
    ):
        self.session = session
        self.organization_id = organization_id
        self.user_id = user_id
        self.project_id = project_id
        self._lock = asyncio.Lock()

    async def run(self, fn: Callable[..., Any], *args: Any) -> Any:
        """Run ``fn(session, *args)`` in a worker thread, one caller at a time."""
        async with self._lock:
            return await anyio.to_thread.run_sync(fn, self.session, *args)

    @asynccontextmanager
    async def spawn_session(self) -> AsyncIterator[Session]:
        """Open a second tenant-scoped session, entered and exited off the loop."""
        async with off_loop_tenant_session(
            self.organization_id, self.user_id, self.project_id
        ) as session:
            yield session


@asynccontextmanager
async def off_loop_tenant_session(
    organization_id: str, user_id: str, project_id: str = ""
) -> AsyncIterator[Session]:
    """A tenant-scoped session whose open and close both happen in a worker thread.

    Opening one runs ``set_config`` and closing it commits or rolls back, so both ends
    are psycopg2 calls that would otherwise block the event loop.
    """
    from rhesis.backend.app.database import get_db_with_tenant_variables

    cm = get_db_with_tenant_variables(organization_id, user_id, project_id)
    session = await anyio.to_thread.run_sync(cm.__enter__)
    try:
        yield session
    except BaseException as exc:
        if not await anyio.to_thread.run_sync(cm.__exit__, type(exc), exc, exc.__traceback__):
            raise
    else:
        await anyio.to_thread.run_sync(cm.__exit__, None, None, None)


def _make_composite_key(
    check_id: str,
    test_set_id: Optional[str] = None,
) -> str:
    if test_set_id and check_id in PER_TEST_SET_CHECKS:
        return f"{check_id}:{test_set_id}"
    return check_id


def _make_result(
    check_id: str,
    status: PreflightCheckStatus,
    message: Optional[str] = None,
    detail: Optional[str] = None,
) -> PreflightCheckResult:
    return PreflightCheckResult(
        check_id=check_id,
        label=LABELS[check_id],
        status=status,
        message=message,
        detail=detail,
    )


async def _publish_check_status(
    correlation_id: str,
    check_id: str,
    status: PreflightCheckStatus,
    message: Optional[str] = None,
    detail: Optional[str] = None,
    test_set_id: Optional[str] = None,
    test_set_name: Optional[str] = None,
    composite_key: Optional[str] = None,
) -> None:
    from rhesis.backend.app.services.websocket.publisher import publish_event_async

    await publish_event_async(
        WebSocketMessage(
            type=EventType.PREFLIGHT_CHECK_UPDATE,
            payload={
                "check_id": check_id,
                "label": LABELS[check_id],
                "status": status.value,
                "message": message,
                "detail": detail,
                "correlation_id": correlation_id,
                "test_set_id": test_set_id,
                "test_set_name": test_set_name,
                "composite_key": composite_key or check_id,
            },
        ),
        ChannelTarget(channel=f"preflight:{correlation_id}"),
    )


def _apply_test_set_fields(
    result: PreflightCheckResult,
    test_set_id: Optional[str] = None,
    test_set_name: Optional[str] = None,
) -> PreflightCheckResult:
    if test_set_id:
        result.test_set_id = test_set_id
        result.test_set_name = test_set_name
        result.composite_key = _make_composite_key(result.check_id, test_set_id)
    else:
        result.composite_key = result.check_id
    return result


async def _publish_result(
    result: PreflightCheckResult,
    correlation_id: Optional[str],
    publish: bool,
) -> None:
    if publish and correlation_id:
        await _publish_check_status(
            correlation_id,
            result.check_id,
            result.status,
            result.message,
            result.detail,
            result.test_set_id,
            result.test_set_name,
            result.composite_key,
        )


async def _verify_model_responds(model) -> None:
    """Send a minimal completion request to verify the model actually works."""
    from rhesis.sdk.models.base import BaseLLM

    if not isinstance(model, BaseLLM):
        return
    await asyncio.wait_for(model.a_generate("Hi", max_tokens=1), timeout=10.0)
