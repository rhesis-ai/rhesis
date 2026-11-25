"""In-flight SDK calls: the record of each one, and when it counts as stranded.

Every dispatched call is recorded in Redis under ``ws:call:{kind}:{run_id}`` with
the scope it was dispatched to. Whichever replica receives the result, and
whichever process waits for it, uses that record: a result is accepted, or a call
given up, only by the one party whose DEL of the record returns 1.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

# How long a call waits once neither its dispatching connection nor any connection
# of its scope is up. Covers the SDK's reconnect backoff and a rolling backend
# restart, and is short next to endpoint timeouts.
DISCONNECT_GRACE_SECONDS = 90.0
# How often a waiter checks whether its call is stranded.
CALL_CHECK_INTERVAL_SECONDS = 5.0
# The record outlives the waiter's own timeout by this much.
CALL_RECORD_MARGIN_SECONDS = 60.0
# Calls dispatched without a timeout: fire-and-forget triggers, and RPC requests
# from pods that predate the timeout field, whose endpoint timeouts capped at 3600s.
DEFAULT_CALL_TIMEOUT_SECONDS = 3600.0

# The result a waiter gets when its connector dropped and never came back.
CONNECTION_LOST_ERROR = "connection_lost"

TEST = "test"
METRIC = "metric"

# Delete KEYS[1] only while it still holds ARGV[1].
_COMPARE_AND_DELETE = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""

# Set KEYS[1] to ARGV[1] with TTL ARGV[2], unless it holds someone else's value.
_REFRESH_IF_OURS = """
local current = redis.call('get', KEYS[1])
if current == false or current == ARGV[1] then
    redis.call('set', KEYS[1], ARGV[1], 'EX', ARGV[2])
    return 1
end
return 0
"""


@dataclass
class PendingCall:
    """A dispatched call waiting for its result."""

    kind: str
    run_id: str
    connection_id: str
    worker_id: str
    organization_id: Optional[str]
    user_id: Optional[str]
    timeout: float = DEFAULT_CALL_TIMEOUT_SECONDS
    project_key: Optional[str] = None
    metric_name: Optional[str] = None
    # Whether an API-process waiter on ``worker_id`` holds an asyncio.Event for it.
    has_local_waiter: bool = False
    # Local bookkeeping, not part of the Redis record.
    expires_at: float = 0.0
    record_written: bool = False
    # The background write of the record (an asyncio.Task), if one was started.
    record_task: Any = field(default=None, repr=False, compare=False)

    @property
    def record_key(self) -> str:
        return call_record_key(self.kind, self.run_id)

    @property
    def record_ttl(self) -> int:
        return int(self.timeout + CALL_RECORD_MARGIN_SECONDS)

    def scope_liveness_key(self) -> Optional[str]:
        """The Redis key that exists while some connection of this scope is up."""
        if self.project_key:
            return f"ws:routing:{self.project_key}"
        if self.organization_id and self.metric_name:
            return f"ws:metric:{self.organization_id}:{self.metric_name}"
        return None

    def to_record(self) -> str:
        return json.dumps(
            {
                "kind": self.kind,
                "run_id": self.run_id,
                "connection_id": self.connection_id,
                "worker_id": self.worker_id,
                "organization_id": self.organization_id,
                "user_id": self.user_id,
                "timeout": self.timeout,
                "project_key": self.project_key,
                "metric_name": self.metric_name,
                "has_local_waiter": self.has_local_waiter,
            }
        )

    @classmethod
    def from_record(cls, raw: str) -> Optional["PendingCall"]:
        try:
            data: Dict[str, Any] = json.loads(raw)
            return cls(
                kind=data["kind"],
                run_id=data["run_id"],
                connection_id=data["connection_id"],
                worker_id=data["worker_id"],
                organization_id=data.get("organization_id"),
                user_id=data.get("user_id"),
                timeout=float(data.get("timeout") or DEFAULT_CALL_TIMEOUT_SECONDS),
                project_key=data.get("project_key"),
                metric_name=data.get("metric_name"),
                has_local_waiter=bool(data.get("has_local_waiter")),
                record_written=True,
            )
        except (ValueError, KeyError, TypeError):
            return None


class StrandedClock:
    """How long a call has had neither its connection nor one of its scope."""

    def __init__(self) -> None:
        self._unreachable_since: Optional[float] = None

    def observe(self, reachable: bool, now: float) -> bool:
        """Record one check; True once the call has been unreachable for the grace."""
        if reachable:
            self._unreachable_since = None
            return False
        if self._unreachable_since is None:
            self._unreachable_since = now
        return now - self._unreachable_since >= DISCONNECT_GRACE_SECONDS


def call_record_key(kind: str, run_id: str) -> str:
    return f"ws:call:{kind}:{run_id}"


async def reachable_via_redis(
    client: Any, call: PendingCall, check_connection: bool = True
) -> bool:
    """Whether the call's dispatching connection, or one of its scope, is up anywhere."""
    if check_connection and await client.exists(f"ws:conn:{call.connection_id}"):
        return True
    key = call.scope_liveness_key()
    return bool(key and await client.exists(key))


async def compare_and_delete(client: Any, key: str, expected: str) -> bool:
    """Delete *key* only if it still holds *expected*; True if it was deleted."""
    return bool(await client.eval(_COMPARE_AND_DELETE, 1, key, expected))


async def refresh_if_ours(client: Any, key: str, value: str, ttl: int) -> bool:
    """Refresh a routing key unless another connection or replica has taken it over."""
    return bool(await client.eval(_REFRESH_IF_OURS, 1, key, value, ttl))


def connection_lost_result() -> Dict[str, Any]:
    return {
        "error": CONNECTION_LOST_ERROR,
        "details": (
            f"The SDK connection closed while the call was running and no connection "
            f"for it came back within {DISCONNECT_GRACE_SECONDS:.0f}s"
        ),
    }
