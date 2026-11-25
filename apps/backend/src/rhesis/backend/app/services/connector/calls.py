"""Tracking of in-flight SDK calls for :class:`ConnectionManager`.

A call is accepted from its dispatching connection, or, once that connection is
gone, from a connection of the same scope: the SDK reconnects with a new
connection id and sends the result there, possibly to another replica. A waiter
whose call has neither connection for ``DISCONNECT_GRACE_SECONDS`` gives up.
"""

import asyncio
import json
import logging
import time
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from rhesis.backend.app.services.connector import pending as pending_calls
from rhesis.backend.app.services.connector.pending import (
    METRIC,
    TEST,
    PendingCall,
    StrandedClock,
    call_record_key,
    connection_lost_result,
    reachable_via_redis,
)
from rhesis.backend.app.services.connector.redis_client import redis_manager
from rhesis.backend.app.services.connector.schemas import ResultAckMessage

logger = logging.getLogger(__name__)

# Expired local entries (calls whose waiter is on another process and gave up) are
# swept at most this often, from the dispatch path.
_PRUNE_INTERVAL_SECONDS = 30.0
_RECORD_WRITE_ATTEMPTS = 3


class Claim(Enum):
    ACCEPT = "accept"
    # Handled for good without resolving anything: late, cancelled, unknown.
    IGNORE = "ignore"
    # Not this connection's to answer, at least not yet. No ack, so the SDK retries.
    REJECT = "reject"


class CallTrackingMixin:
    """In-flight call bookkeeping. Relies on ConnectionManager's state."""

    _pending: Dict[str, Dict[str, PendingCall]]
    _ack_connections: set
    _last_prune: float

    # --- Dispatch ---

    def _register_call(
        self,
        kind: str,
        run_id: str,
        connection_id: str,
        timeout: Optional[float],
        project_key: Optional[str] = None,
        metric_name: Optional[str] = None,
    ) -> PendingCall:
        """Record a call before it is sent: locally now, in Redis in the background."""
        context = self._contexts.get(connection_id)
        call = PendingCall(
            kind=kind,
            run_id=run_id,
            connection_id=connection_id,
            worker_id=self.worker_id,
            organization_id=context.organization_id if context else None,
            user_id=context.user_id if context else None,
            timeout=float(timeout or pending_calls.DEFAULT_CALL_TIMEOUT_SECONDS),
            project_key=project_key,
            metric_name=metric_name,
            has_local_waiter=run_id in self._result_events,
        )
        call.expires_at = time.monotonic() + call.record_ttl
        self._prune_expired_calls()
        self._pending[kind][run_id] = call
        if redis_manager.is_available:
            # Not awaited: the dispatching connection answers from the local entry, and
            # another replica only sees the result after a reconnect (>= 0.5s), by
            # which time the record has landed.
            call.record_task = self._track_background_task(self._write_call_record(call))
        return call

    async def _write_call_record(self, call: PendingCall) -> None:
        for attempt in range(_RECORD_WRITE_ATTEMPTS):
            try:
                await redis_manager.client.setex(call.record_key, call.record_ttl, call.to_record())
                call.record_written = True
                return
            except Exception as e:
                last_error = e
                if attempt + 1 < _RECORD_WRITE_ATTEMPTS:
                    await asyncio.sleep(0.2 * 2**attempt)
        # Without a record, a result arriving on another replica after a reconnect
        # reads as "already handled" there and is acked away; only the dispatching
        # connection can still deliver it.
        logger.error(f"Failed to record {call.kind} call {call.run_id}: {last_error}")

    def _prune_expired_calls(self) -> None:
        now = time.monotonic()
        if now - self._last_prune < _PRUNE_INTERVAL_SECONDS:
            return
        self._last_prune = now
        for pending in self._pending.values():
            for run_id in [r for r, c in pending.items() if c.expires_at < now]:
                pending.pop(run_id, None)

    def _release_pending(self, kind: str, run_id: str) -> None:
        """Forget a call whose waiter is done with it."""
        call = self._pending[kind].pop(run_id, None)
        if call is not None:
            self._drop_call_record(call)

    def _drop_call_record(self, call: PendingCall) -> None:
        """Delete the call's Redis record in the background, after it was written."""
        if call.record_task is None or not redis_manager.is_available:
            return
        try:
            self._track_background_task(self._delete_call_record(call))
        except RuntimeError:
            pass  # No running loop; the record expires on its own.

    async def _delete_call_record(self, call: PendingCall) -> None:
        await asyncio.wait({call.record_task})
        if call.record_written:
            await redis_manager.client.delete(call.record_key)

    # --- Results ---

    async def _accept_result(
        self, kind: str, run_id: str, connection_id: str, message: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Resolve the waiter if *connection_id* may answer. Returns (accepted, ack)."""
        outcome, call = self._claim_local(kind, run_id, connection_id)
        if outcome is None:
            outcome, call = await self._claim(kind, run_id, connection_id)
        if outcome is Claim.ACCEPT:
            self._resolver(kind)(run_id, message)
            await self._deliver_to_dispatching_worker(call, message)
        if outcome is Claim.REJECT or connection_id not in self._ack_connections:
            return outcome is Claim.ACCEPT, None
        field = "test_run_id" if kind == TEST else "metric_run_id"
        return outcome is Claim.ACCEPT, ResultAckMessage(**{field: run_id}).model_dump()

    def _claim_local(
        self, kind: str, run_id: str, connection_id: str
    ) -> Tuple[Optional[Claim], Optional[PendingCall]]:
        """The common case, with no Redis round trip: the dispatching connection answers.

        The entry is ours to take: another replica may only claim the call once
        this connection is gone, and a waiter giving up pops the entry first.
        """
        call = self._pending[kind].get(run_id)
        if call is None or call.connection_id != connection_id:
            return None, None
        self._pending[kind].pop(run_id, None)
        self._drop_call_record(call)
        return Claim.ACCEPT, call

    async def _claim(
        self, kind: str, run_id: str, connection_id: str
    ) -> Tuple[Claim, Optional[PendingCall]]:
        call = self._pending[kind].get(run_id)
        local = call is not None
        if call is None:
            try:
                call = await self._read_call_record(kind, run_id)
            except Exception as e:
                # Unknown is not "absent": no ack, so the SDK sends it again.
                logger.warning(f"Failed to read {kind} call {run_id}: {e}")
                return Claim.REJECT, None
        if call is None:
            # Unknown here and in Redis: answered, given up, or expired.
            if self._is_registered(connection_id):
                return Claim.IGNORE, None
            return Claim.REJECT, None
        if not await self._may_answer(call, connection_id):
            logger.warning(
                "%s_result rejected: connection may not answer this call "
                "(run_id=%s, dispatched_on=%s, got=%s)",
                kind,
                run_id,
                call.connection_id,
                connection_id,
            )
            return Claim.REJECT, None
        taken = await self._take(call, local=local)
        if taken is None:
            return Claim.REJECT, None
        if not taken:
            return Claim.IGNORE, None
        logger.info(
            "Accepted %s result %s on %s for a call dispatched on %s",
            kind,
            run_id,
            connection_id,
            call.connection_id,
        )
        return Claim.ACCEPT, call

    async def _take(self, call: PendingCall, local: bool) -> Optional[bool]:
        """Claim *call* for resolution. True if won, False if someone else had it,
        None if Redis could not say.

        *local*: the call came from this replica's table, so losing the entry to a
        local claim during the awaits below also counts as losing.
        """
        pending = self._pending[call.kind]
        if call.record_task is not None:
            await asyncio.wait({call.record_task})
        if not call.record_written or not redis_manager.is_available:
            return pending.pop(call.run_id, None) is not None
        try:
            won = bool(await redis_manager.client.delete(call.record_key))
        except Exception as e:
            logger.warning(f"Failed to claim {call.kind} call {call.run_id}: {e}")
            return None
        popped = pending.pop(call.run_id, None) is not None
        return won and (popped or not local)

    async def _read_call_record(self, kind: str, run_id: str) -> Optional[PendingCall]:
        """The call's Redis record, or None if there is none. Raises on Redis errors."""
        if not redis_manager.is_available:
            return None
        raw = await redis_manager.client.get(call_record_key(kind, run_id))
        return PendingCall.from_record(raw) if raw else None

    def _is_registered(self, connection_id: str) -> bool:
        return bool(
            self._connection_projects.get(connection_id)
            or self._connection_metric_keys.get(connection_id)
        )

    async def _may_answer(self, call: PendingCall, connection_id: str) -> bool:
        """The dispatching connection may; another only once that one is gone,
        and only within the call's scope."""
        if connection_id == call.connection_id:
            return True
        context = self._contexts.get(connection_id)
        if connection_id not in self._connections or context is None:
            return False
        if not call.organization_id or context.organization_id != call.organization_id:
            return False
        if call.project_key:
            in_scope = call.project_key in self._connection_projects.get(connection_id, set())
        else:
            metric_keys = self._connection_metric_keys.get(connection_id, set())
            in_scope = (
                bool(call.metric_name)
                and context.user_id == call.user_id
                and (call.organization_id, call.metric_name) in metric_keys
            )
        return in_scope and not await self._connection_alive(call)

    async def _connection_alive(self, call: PendingCall) -> bool:
        if call.connection_id in self._connections:
            return True
        if call.worker_id == self.worker_id or not redis_manager.is_available:
            return False  # Dispatched here: the local table is the truth.
        try:
            return bool(await redis_manager.client.exists(f"ws:conn:{call.connection_id}"))
        except Exception:
            return True  # Unknown counts as alive: the SDK retries the result later.

    def _resolver(self, kind: str):
        return self._resolve_test_result if kind == TEST else self._resolve_metric_result

    async def _deliver_to_dispatching_worker(
        self, call: PendingCall, result: Dict[str, Any]
    ) -> None:
        """Hand a result to the replica whose in-process waiter is blocked on it.

        The Redis publish in ``_resolve_*`` reaches RPC waiters; an API-process
        waiter on the dispatching replica only listens to its local asyncio.Event.
        """
        if not call.has_local_waiter or call.worker_id == self.worker_id:
            return
        if not redis_manager.is_available:
            return
        payload = {
            "request_type": "deliver_result",
            "kind": call.kind,
            "request_id": call.run_id,
            "result": result,
        }
        try:
            await redis_manager.client.rpush(f"ws:rpc:{call.worker_id}", json.dumps(payload))
        except Exception as e:
            logger.warning(f"Failed to hand {call.kind} result {call.run_id} over: {e}")

    def _accept_delivered_result(self, request: Dict[str, Any]) -> None:
        """Wake the local waiter for a result another replica accepted."""
        kind = request.get("kind")
        run_id = request.get("request_id")
        result = request.get("result")
        if kind not in self._pending or not run_id or not isinstance(result, dict):
            return
        self._pending[kind].pop(run_id, None)
        if run_id in self._result_events:
            # The accepting replica already published it for RPC waiters.
            self._resolver(kind)(run_id, result, publish=False)

    # --- Waiting ---

    async def _wait_for_result(
        self, kind: str, run_id: str, event: asyncio.Event, timeout: float
    ) -> Optional[Dict[str, Any]]:
        """Wait for *event*. Returns an error result if the call is given up first.

        Raises ``asyncio.TimeoutError`` after *timeout*.
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        clock = StrandedClock()
        while not event.is_set():
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise asyncio.TimeoutError
            interval = min(pending_calls.CALL_CHECK_INTERVAL_SECONDS, remaining)
            try:
                await asyncio.wait_for(event.wait(), interval)
            except asyncio.TimeoutError:
                if not event.is_set() and await self._give_up_if_stranded(kind, run_id, clock):
                    return connection_lost_result()
        return None

    async def _give_up_if_stranded(self, kind: str, run_id: str, clock: StrandedClock) -> bool:
        call = self._pending[kind].get(run_id)
        if call is None:
            return False  # Claimed: the result is on its way.
        reachable = await self._call_reachable(call)
        if not clock.observe(reachable, time.monotonic()):
            return False
        # Giving up must win the claim, or a result was accepted meanwhile.
        if not await self._take(call, local=True):
            return False
        logger.warning(
            "Giving up %s call %s: connection %s dropped and none of its scope "
            "came back within %.0fs",
            kind,
            run_id,
            call.connection_id,
            pending_calls.DISCONNECT_GRACE_SECONDS,
        )
        return True

    async def _call_reachable(self, call: PendingCall) -> bool:
        if call.connection_id in self._connections:
            return True
        if call.project_key and self._project_routing.get(call.project_key) in self._connections:
            return True
        if not call.project_key and call.metric_name:
            wanted = (call.organization_id, call.metric_name)
            for conn_id, keys in self._connection_metric_keys.items():
                if wanted in keys and conn_id in self._connections:
                    return True
        if not redis_manager.is_available:
            return False
        try:
            # The dispatching replica already knows its own connection is gone.
            return await reachable_via_redis(
                redis_manager.client, call, check_connection=call.worker_id != self.worker_id
            )
        except Exception:
            return True  # Unknown counts as reachable; the timeout still applies.


__all__ = ["CallTrackingMixin", "Claim", "METRIC", "TEST"]
