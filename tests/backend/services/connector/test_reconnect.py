"""Connector calls survive the SDK reconnecting, and fail fast when it does not."""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from rhesis.backend.app.services.connector import calls as calls_module
from rhesis.backend.app.services.connector import pending as pending_calls
from rhesis.backend.app.services.connector.manager import ConnectionManager
from rhesis.backend.app.services.connector.pending import METRIC, TEST
from rhesis.backend.app.services.connector.rpc_client import SDKRpcClient
from rhesis.backend.app.services.connector.schemas import WebSocketConnectionContext

ORG = "org-1"
PROJECT_KEY = "project-1:development"


class FakeRedis:
    """Just enough of redis.asyncio for call records, routing keys and hand-offs."""

    def __init__(self):
        self.values = {}
        self.ttls = {}
        self.lists = {}
        self.published = []
        self.on_exists = None

    fail = False  # raise on every command, like a saturated pool

    def _command(self):
        if self.fail:
            raise ConnectionError("pool exhausted")

    async def setex(self, key, ttl, value):
        self._command()
        self.values[key] = value
        self.ttls[key] = ttl

    async def get(self, key):
        self._command()
        return self.values.get(key)

    async def exists(self, key):
        self._command()
        if self.on_exists:
            self.on_exists(key)
        return int(key in self.values)

    async def delete(self, key):
        self._command()
        return int(self.values.pop(key, None) is not None)

    async def eval(self, script, numkeys, key, value, *ttl):
        self._command()
        current = self.values.get(key)
        if ttl:  # refresh_if_ours
            if current in (None, value):
                self.values[key] = value
                return 1
            return 0
        if current == value:  # compare_and_delete
            return int(self.values.pop(key, None) is not None)
        return 0

    async def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    async def publish(self, channel, value):
        self.published.append((channel, json.loads(value)))


@pytest.fixture
def redis(mock_redis):
    fake = FakeRedis()
    mock_redis.is_available = True
    mock_redis.client = fake
    return fake


@pytest.fixture
def fast_grace():
    with (
        patch.object(pending_calls, "DISCONNECT_GRACE_SECONDS", 0.1),
        patch.object(pending_calls, "CALL_CHECK_INTERVAL_SECONDS", 0.02),
    ):
        yield


def _connect(
    manager,
    conn_id,
    org=ORG,
    project_key=PROJECT_KEY,
    user="user-1",
    acks=True,
    redis=None,
    register=True,
):
    """Put a connection on *manager* without the network handshake."""
    manager._connections[conn_id] = AsyncMock()
    manager._contexts[conn_id] = WebSocketConnectionContext(
        connection_id=conn_id, user_id=user, organization_id=org
    )
    if acks:
        manager._ack_connections.add(conn_id)
    if redis is not None:
        redis.values[f"ws:conn:{conn_id}"] = manager.worker_id
    if register:
        manager._connection_projects[conn_id] = {project_key}
        manager._project_routing[project_key] = conn_id
        if redis is not None:
            redis.values[f"ws:routing:{project_key}"] = manager.worker_id
    else:
        manager._connection_projects[conn_id] = set()


async def _drop(manager, conn_id):
    manager.disconnect_by_connection_id(conn_id)
    await asyncio.sleep(0)  # let the Redis cleanup run


async def _send_result(manager, conn_id, run_id, kind=TEST):
    message = (
        {"type": "test_result", "test_run_id": run_id, "status": "success"}
        if kind == TEST
        else {"type": "metric_result", "metric_run_id": run_id, "status": "success"}
    )
    with patch("rhesis.backend.app.services.connector.manager.message_handler") as handler:
        handler.handle_test_result_message = AsyncMock()
        return await manager.handle_message(
            connection_id=conn_id,
            message=message,
            db_factory=Mock(side_effect=AssertionError("no session expected")),
        )


async def _dispatch(manager, run_id, timeout=5.0):
    """Start a direct-path call and wait until it is recorded."""
    waiter = asyncio.create_task(
        manager.send_and_await_result("project-1", "development", run_id, "fn", {}, timeout)
    )
    for _ in range(100):
        if run_id in manager._pending[TEST]:
            return waiter
        await asyncio.sleep(0)
    raise AssertionError("call was never dispatched")


async def _dispatch_rpc(manager, run_id, timeout=None):
    request = {
        "request_id": run_id,
        "function_name": "fn",
        "inputs": {},
        "project_id": "project-1",
        "environment": "development",
    }
    if timeout is not None:
        request["timeout"] = timeout
    await manager._handle_rpc_request(request)


# --- Acceptance on a new connection (C) ---


@pytest.mark.asyncio
async def test_result_on_a_new_connection_of_the_same_scope_resolves_the_waiter():
    manager = ConnectionManager()
    _connect(manager, "conn-a")
    waiter = await _dispatch(manager, "run-1")

    await _drop(manager, "conn-a")
    _connect(manager, "conn-b")
    ack = await _send_result(manager, "conn-b", "run-1")

    assert (await asyncio.wait_for(waiter, timeout=1))["status"] == "success"
    assert ack == {"type": "result_ack", "test_run_id": "run-1", "metric_run_id": None}
    assert "run-1" not in manager._pending[TEST]


@pytest.mark.asyncio
async def test_result_on_a_new_connection_is_published_for_rpc_waiters(redis):
    manager = ConnectionManager()
    _connect(manager, "conn-a", redis=redis)
    await _dispatch_rpc(manager, "run-rpc", timeout=10)
    await _drop(manager, "conn-a")
    _connect(manager, "conn-b", redis=redis)

    await _send_result(manager, "conn-b", "run-rpc")
    await asyncio.sleep(0)

    [(channel, result)] = redis.published
    assert channel == "ws:rpc:response:run-rpc"
    assert result["status"] == "success"
    assert "ws:call:test:run-rpc" not in redis.values


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "org, project_key",
    [("org-2", PROJECT_KEY), (ORG, "project-2:development"), (ORG, "project-1:production")],
    ids=["other-org", "other-project", "other-environment"],
)
async def test_result_from_another_scope_is_rejected(caplog, org, project_key):
    manager = ConnectionManager()
    _connect(manager, "conn-a")
    waiter = await _dispatch(manager, "run-1", timeout=0.2)
    await _drop(manager, "conn-a")
    _connect(manager, "conn-x", org=org, project_key=project_key)

    with caplog.at_level("WARNING"):
        ack = await _send_result(manager, "conn-x", "run-1")

    assert ack is None
    assert "test_result rejected" in caplog.text
    assert await waiter == {"error": "timeout"}


@pytest.mark.asyncio
async def test_same_scope_connection_cannot_answer_while_the_dispatcher_is_alive():
    """Finding 5: only the dispatching connection may answer while it is up."""
    manager = ConnectionManager()
    _connect(manager, "conn-a")
    waiter = await _dispatch(manager, "run-1")
    _connect(manager, "conn-b")  # a second SDK process for the same project:env

    assert await _send_result(manager, "conn-b", "run-1") is None
    assert not waiter.done()
    await _send_result(manager, "conn-a", "run-1")
    assert (await asyncio.wait_for(waiter, timeout=1))["status"] == "success"


# --- Acks (A) ---


@pytest.mark.asyncio
async def test_register_advertises_and_records_acks():
    manager = ConnectionManager()
    _connect(manager, "conn-a", acks=False, register=False)
    for conn_id, asks in (("conn-a", True), ("conn-b", False)):
        _connect(manager, conn_id, acks=False, register=False)
        with patch.object(
            manager, "_handle_register_message", AsyncMock(return_value={"type": "registered"})
        ):
            response = await manager.handle_message(
                connection_id=conn_id, message={"type": "register", "result_ack": asks}
            )
        assert response["result_ack"] is True
    assert manager._ack_connections == {"conn-a"}


@pytest.mark.asyncio
async def test_late_result_for_an_unknown_call_is_acked_and_ignored():
    manager = ConnectionManager()
    _connect(manager, "conn-a")
    with patch.object(manager, "_resolve_test_result") as resolve:
        ack = await _send_result(manager, "conn-a", "run-gone")
    resolve.assert_not_called()
    assert ack["test_run_id"] == "run-gone"


@pytest.mark.asyncio
async def test_result_on_an_unregistered_connection_is_not_acked():
    """Finding 1: sent before `register` was processed, so the SDK must resend it."""
    manager = ConnectionManager()
    _connect(manager, "conn-a")
    waiter = await _dispatch(manager, "run-1")
    await _drop(manager, "conn-a")
    _connect(manager, "conn-b", register=False)

    assert await _send_result(manager, "conn-b", "run-1") is None
    assert await _send_result(manager, "conn-b", "run-unknown") is None

    manager._connection_projects["conn-b"] = {PROJECT_KEY}  # now registered
    assert await _send_result(manager, "conn-b", "run-1") is not None
    assert (await asyncio.wait_for(waiter, timeout=1))["status"] == "success"


@pytest.mark.asyncio
async def test_no_ack_for_a_connection_that_did_not_ask():
    manager = ConnectionManager()
    _connect(manager, "conn-a", acks=False)
    await _dispatch(manager, "run-1")
    assert await _send_result(manager, "conn-a", "run-1") is None


# --- Another replica (B) ---


@pytest.mark.asyncio
async def test_result_reaches_another_replica_before_the_old_one_notices(redis):
    """Finding 4: replica B gets the result while A still holds the old socket.

    B refuses while ``ws:conn`` says the dispatching connection is up (no ack, so the
    SDK resends), and accepts once it is gone, even if A never ran its teardown.
    """
    replica_a, replica_b = ConnectionManager(), ConnectionManager()
    _connect(replica_a, "conn-a", redis=redis)
    waiter = await _dispatch(replica_a, "run-1")
    await asyncio.sleep(0)  # the record is written in the background
    assert "ws:call:test:run-1" in redis.values

    _connect(replica_b, "conn-b", redis=redis)
    assert await _send_result(replica_b, "conn-b", "run-1") is None

    del redis.values["ws:conn:conn-a"]  # expired: A died without a teardown
    ack = await _send_result(replica_b, "conn-b", "run-1")
    assert ack["test_run_id"] == "run-1"
    assert "ws:call:test:run-1" not in redis.values

    [handoff] = redis.lists[f"ws:rpc:{replica_a.worker_id}"]
    await replica_a._handle_rpc_request(json.loads(handoff))
    assert (await asyncio.wait_for(waiter, timeout=1))["status"] == "success"


@pytest.mark.asyncio
async def test_record_from_another_scope_is_not_claimed(redis):
    replica_a, replica_b = ConnectionManager(), ConnectionManager()
    _connect(replica_a, "conn-a", redis=redis)
    await _dispatch_rpc(replica_a, "run-1", timeout=10)
    await _drop(replica_a, "conn-a")

    _connect(replica_b, "conn-x", org="org-2", redis=redis)
    with patch.object(replica_b, "_resolve_test_result") as resolve:
        assert await _send_result(replica_b, "conn-x", "run-1") is None

    resolve.assert_not_called()
    assert "ws:call:test:run-1" in redis.values


@pytest.mark.asyncio
async def test_only_one_replica_claims_a_result(redis):
    replica_a, replica_b = ConnectionManager(), ConnectionManager()
    _connect(replica_a, "conn-a", redis=redis)
    await _dispatch_rpc(replica_a, "run-1", timeout=10)
    await _drop(replica_a, "conn-a")
    _connect(replica_b, "conn-b", redis=redis)
    _connect(replica_a, "conn-c", redis=redis)

    await _send_result(replica_b, "conn-b", "run-1")
    with patch.object(replica_a, "_resolve_test_result") as resolve:
        ack = await _send_result(replica_a, "conn-c", "run-1")
    resolve.assert_not_called()
    assert ack is not None  # handled for good elsewhere


# --- Records carry the call's own timeout (B) ---


@pytest.mark.asyncio
async def test_call_record_ttl_follows_the_call_timeout(redis):
    manager = ConnectionManager()
    _connect(manager, "conn-a", redis=redis)
    await _dispatch_rpc(manager, "run-long", timeout=7200)
    await _dispatch_rpc(manager, "run-old-pod")
    await asyncio.sleep(0)  # records are written in the background

    margin = pending_calls.CALL_RECORD_MARGIN_SECONDS
    assert redis.ttls["ws:call:test:run-long"] == int(7200 + margin)
    assert redis.ttls["ws:call:test:run-old-pod"] == int(
        pending_calls.DEFAULT_CALL_TIMEOUT_SECONDS + margin
    )


@pytest.mark.asyncio
async def test_rpc_request_carries_its_timeout():
    client = SDKRpcClient()
    client._redis = FakeRedis()
    client._redis.values["ws:routing:project-1:development"] = "worker-a"
    pubsub = Mock(
        subscribe=AsyncMock(),
        unsubscribe=AsyncMock(),
        close=AsyncMock(),
        get_message=AsyncMock(return_value=None),
    )
    client._redis.pubsub = Mock(return_value=pubsub)
    client._redis.values["ws:call:test:run-1"] = "placeholder"

    result = await client.send_and_await_result(
        "project-1", "development", "run-1", "fn", {}, timeout=0.05
    )

    assert result == {"error": "timeout"}
    [request] = client._redis.lists["ws:rpc:worker-a"]
    assert json.loads(request)["timeout"] == 0.05
    # Finding 10: the waiter that gives up drops the call record.
    assert "ws:call:test:run-1" not in client._redis.values


@pytest.mark.asyncio
async def test_rpc_dispatched_calls_are_released_after_their_timeout():
    """Finding 10: the waiter is in Celery, so nothing here ever pops these entries."""
    manager = ConnectionManager()
    _connect(manager, "conn-a")
    with (
        patch.object(pending_calls, "CALL_RECORD_MARGIN_SECONDS", 0),
        patch.object(calls_module, "_PRUNE_INTERVAL_SECONDS", 0),
    ):
        await _dispatch_rpc(manager, "run-old", timeout=0.01)
        await asyncio.sleep(0.02)
        await _dispatch_rpc(manager, "run-new", timeout=10)
    assert set(manager._pending[TEST]) == {"run-new"}


# --- Routes survive the old socket's teardown (9) ---


@pytest.mark.asyncio
async def test_old_socket_teardown_keeps_the_new_connections_route(redis):
    manager = ConnectionManager()
    _connect(manager, "conn-a", redis=redis)
    _connect(manager, "conn-b", redis=redis)  # re-registered the same project:env

    await _drop(manager, "conn-a")

    assert manager._project_routing[PROJECT_KEY] == "conn-b"
    assert f"ws:routing:{PROJECT_KEY}" in redis.values


@pytest.mark.asyncio
async def test_teardown_leaves_a_route_another_replica_took_over(redis):
    manager = ConnectionManager()
    _connect(manager, "conn-a", redis=redis)
    manager._connection_metric_keys["conn-a"] = {(ORG, "m")}
    redis.values[f"ws:routing:{PROJECT_KEY}"] = "other-replica"
    redis.values[f"ws:metric:{ORG}:m"] = "conn-elsewhere"

    await _drop(manager, "conn-a")

    assert redis.values[f"ws:routing:{PROJECT_KEY}"] == "other-replica"
    assert redis.values[f"ws:metric:{ORG}:m"] == "conn-elsewhere"
    assert "ws:conn:conn-a" not in redis.values


# --- Giving up after the grace (B) ---


@pytest.mark.asyncio
async def test_disconnect_without_reconnect_fails_the_waiter_early(fast_grace):
    manager = ConnectionManager()
    _connect(manager, "conn-a")
    waiter = await _dispatch(manager, "run-1", timeout=5)

    await _drop(manager, "conn-a")
    result = await asyncio.wait_for(waiter, timeout=1)

    assert result["error"] == "connection_lost"
    _connect(manager, "conn-b")
    with patch.object(manager, "_resolve_test_result") as resolve:
        ack = await _send_result(manager, "conn-b", "run-1")
    resolve.assert_not_called()
    assert ack is not None  # the late result is acked and ignored


@pytest.mark.asyncio
async def test_reconnect_within_the_grace_keeps_the_call_waiting(fast_grace):
    manager = ConnectionManager()
    _connect(manager, "conn-a")
    waiter = await _dispatch(manager, "run-1", timeout=5)

    await _drop(manager, "conn-a")
    _connect(manager, "conn-b")
    await asyncio.sleep(0.3)  # three graces
    assert not waiter.done()

    await _send_result(manager, "conn-b", "run-1")
    assert (await asyncio.wait_for(waiter, timeout=1))["status"] == "success"


@pytest.mark.asyncio
async def test_giving_up_loses_to_a_result_claimed_meanwhile(fast_grace, redis):
    """Finding 6: another replica claims the result while the waiter checks liveness."""
    manager = ConnectionManager()
    _connect(manager, "conn-a", redis=redis)
    waiter = await _dispatch(manager, "run-1", timeout=5)
    await _drop(manager, "conn-a")

    def claim_during_the_check(key):
        redis.values.pop("ws:call:test:run-1", None)  # replica B's DEL wins

    redis.on_exists = claim_during_the_check
    await asyncio.sleep(0.3)  # three graces
    assert not waiter.done()

    await manager._handle_rpc_request(
        {
            "request_type": "deliver_result",
            "kind": TEST,
            "request_id": "run-1",
            "result": {"type": "test_result", "test_run_id": "run-1", "status": "success"},
        }
    )
    assert (await asyncio.wait_for(waiter, timeout=1))["status"] == "success"


class _SilentPubSub:
    subscribe = AsyncMock()
    unsubscribe = AsyncMock()
    close = AsyncMock()

    async def get_message(self, ignore_subscribe_messages, timeout):
        await asyncio.sleep(timeout)


@pytest.mark.asyncio
async def test_rpc_waiter_gives_up_when_the_connector_does_not_return(fast_grace, redis):
    """The Celery waiter fails fast even when the socket's replica is gone too."""
    manager = ConnectionManager()
    _connect(manager, "conn-a", redis=redis)
    await _dispatch_rpc(manager, "run-1", timeout=10)
    del redis.values["ws:conn:conn-a"]
    del redis.values[f"ws:routing:{PROJECT_KEY}"]

    client = SDKRpcClient()
    client._redis = redis
    result = await asyncio.wait_for(
        client._await_response(_SilentPubSub(), TEST, "run-1", timeout=5), timeout=1
    )

    assert result["error"] == "connection_lost"
    assert "ws:call:test:run-1" not in redis.values


@pytest.mark.asyncio
async def test_rpc_waiter_keeps_waiting_while_the_scope_is_up(fast_grace, redis):
    manager = ConnectionManager()
    _connect(manager, "conn-a", redis=redis)
    await _dispatch_rpc(manager, "run-1", timeout=10)
    del redis.values["ws:conn:conn-a"]  # the old socket is gone, the route is held elsewhere

    client = SDKRpcClient()
    client._redis = redis
    with pytest.raises(asyncio.TimeoutError):
        await client._await_response(_SilentPubSub(), TEST, "run-1", timeout=0.3)
    assert "ws:call:test:run-1" in redis.values


@pytest.mark.asyncio
async def test_metric_waiter_gives_up_too(fast_grace):
    manager = ConnectionManager()
    _connect(manager, "conn-a")
    manager._connection_metric_keys["conn-a"] = {(ORG, "m")}
    waiter = asyncio.create_task(
        manager.send_and_await_metric_by_connection("conn-a", "metric-1", "m", {}, timeout=5)
    )
    await asyncio.sleep(0)
    await _drop(manager, "conn-a")
    result = await asyncio.wait_for(waiter, timeout=1)
    assert result["error"] == "connection_lost"
    assert "metric-1" not in manager._pending[METRIC]


# --- Second review ---


@pytest.mark.asyncio
async def test_redis_error_reading_the_record_rejects_without_ack(redis):
    """A failed GET is not "no such call": the SDK must keep the result and resend it."""
    replica_a, replica_b = ConnectionManager(), ConnectionManager()
    _connect(replica_a, "conn-a", redis=redis)
    await _dispatch_rpc(replica_a, "run-1", timeout=10)
    await asyncio.sleep(0)
    await _drop(replica_a, "conn-a")
    _connect(replica_b, "conn-b", redis=redis)

    redis.fail = True
    assert await _send_result(replica_b, "conn-b", "run-1") is None
    redis.fail = False
    ack = await _send_result(replica_b, "conn-b", "run-1")
    assert ack["test_run_id"] == "run-1"


@pytest.mark.asyncio
async def test_failed_record_write_is_retried(redis):
    failures = [ConnectionError("pool exhausted")]
    setex = redis.setex

    async def flaky_setex(key, ttl, value):
        if failures:
            raise failures.pop()
        await setex(key, ttl, value)

    redis.setex = flaky_setex
    manager = ConnectionManager()
    _connect(manager, "conn-a", redis=redis)
    await _dispatch_rpc(manager, "run-1", timeout=10)
    await asyncio.sleep(0.3)
    assert "ws:call:test:run-1" in redis.values


@pytest.mark.asyncio
async def test_result_on_the_dispatching_connection_needs_no_redis(redis):
    """Item 2: the common path resolves even while every Redis command fails."""
    manager = ConnectionManager()
    _connect(manager, "conn-a", redis=redis)
    waiter = await _dispatch(manager, "run-1")
    await asyncio.sleep(0)

    redis.fail = True
    ack = await _send_result(manager, "conn-a", "run-1")

    assert ack["test_run_id"] == "run-1"
    assert (await asyncio.wait_for(waiter, timeout=1))["status"] == "success"
    redis.fail = False
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_rpc_dispatch_does_not_wait_for_the_record(redis):
    """Item 2: the BLPOP listener forwards without awaiting Redis."""
    stuck = asyncio.Event()

    async def blocked_setex(key, ttl, value):
        await stuck.wait()

    redis.setex = blocked_setex
    manager = ConnectionManager()
    _connect(manager, "conn-a", redis=redis)

    await asyncio.wait_for(_dispatch_rpc(manager, "run-1", timeout=10), timeout=0.5)

    manager._connections["conn-a"].send_json.assert_awaited_once()
    stuck.set()
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_stale_route_is_no_longer_refreshed_or_torn_down(redis):
    """Item 4: after a failed send drops the route, the heartbeat must not revive it."""
    manager = ConnectionManager()
    _connect(manager, "conn-a", redis=redis)

    await manager._cleanup_stale_routing(PROJECT_KEY)
    await manager._refresh_routes("conn-a")
    assert f"ws:routing:{PROJECT_KEY}" not in redis.values

    redis.values[f"ws:routing:{PROJECT_KEY}"] = "other-replica"
    await _drop(manager, "conn-a")
    assert redis.values[f"ws:routing:{PROJECT_KEY}"] == "other-replica"


@pytest.mark.asyncio
async def test_old_connection_heartbeat_does_not_take_routes_back(redis):
    """Item 5: the SDK reconnected elsewhere; the lingering old socket keeps beating."""
    manager = ConnectionManager()
    _connect(manager, "conn-a", redis=redis)
    manager._connection_metric_keys["conn-a"] = {(ORG, "m")}
    redis.values[f"ws:routing:{PROJECT_KEY}"] = "other-replica"
    redis.values[f"ws:metric:{ORG}:m"] = "conn-new"

    await manager._refresh_routes("conn-a")

    assert redis.values[f"ws:routing:{PROJECT_KEY}"] == "other-replica"
    assert redis.values[f"ws:metric:{ORG}:m"] == "conn-new"


@pytest.mark.asyncio
async def test_old_connection_heartbeat_skips_a_route_taken_locally(redis):
    manager = ConnectionManager()
    _connect(manager, "conn-a", redis=redis)
    _connect(manager, "conn-b", redis=redis)
    del redis.values[f"ws:routing:{PROJECT_KEY}"]

    await manager._refresh_routes("conn-a")
    assert f"ws:routing:{PROJECT_KEY}" not in redis.values
    await manager._refresh_routes("conn-b")
    assert redis.values[f"ws:routing:{PROJECT_KEY}"] == manager.worker_id


@pytest.mark.asyncio
async def test_connection_closed_during_registration_is_not_marked_for_acks():
    """Item 8: registration awaits the database; the socket may be gone by then."""
    manager = ConnectionManager()
    _connect(manager, "conn-a", acks=False, register=False)

    async def register_while_closing(**kwargs):
        manager.disconnect_by_connection_id("conn-a")
        return {"type": "registered"}

    with patch.object(manager, "_handle_register_message", register_while_closing):
        await manager.handle_message(
            connection_id="conn-a", message={"type": "register", "result_ack": True}
        )
    assert "conn-a" not in manager._ack_connections
