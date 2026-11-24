"""Results reach the backend across reconnects: kept until acknowledged, resent paced."""

import asyncio
from unittest.mock import patch

import pytest
from websockets.exceptions import ConnectionClosedError

from rhesis.sdk.connector import outbox as outbox_module
from rhesis.sdk.connector.manager import ConnectorManager
from rhesis.sdk.connector.outbox import ResultOutbox
from rhesis.sdk.connector.schemas import RegisterMessage
from rhesis.sdk.connector.types import ConnectionState


class FakeConnection:
    """Stands in for WebSocketConnection: one socket object per connection."""

    def __init__(self):
        self.websocket = object()
        self.state = ConnectionState.CONNECTED
        self.up = True
        self.sent = []

    async def send(self, message):
        if not self.up:
            raise RuntimeError("WebSocket not connected")
        self.sent.append(message)

    def drop(self):
        self.up = False
        self.state = ConnectionState.RECONNECTING

    def reconnect(self):
        self.websocket = object()
        self.up = True
        self.state = ConnectionState.CONNECTED


def _run_ids(messages):
    return [m.get("test_run_id") or m.get("metric_run_id") for m in messages]


@pytest.fixture
def manager():
    mgr = ConnectorManager(api_key="key", project_id="project-1", base_url="http://localhost")
    mgr._connection = FakeConnection()
    yield mgr
    for task in mgr._background_tasks:
        task.cancel()


async def _registered(manager, acks=True):
    await manager._handle_message({"type": "registered", "status": "success", "result_ack": acks})
    # Let the flush run; the resend loop sleeps, so it never finishes on its own.
    for _ in range(5):
        await asyncio.sleep(0)


def test_register_message_asks_for_acks():
    assert RegisterMessage(functions=[]).model_dump()["result_ack"] is True


# --- With acks (backend advertises result_ack) ---


@pytest.mark.asyncio
async def test_result_is_kept_until_acked(manager):
    await _registered(manager)
    await manager._send_test_result("run-1", status="success", output="x")

    assert "run-1" in manager._outbox
    await manager._handle_message({"type": "result_ack", "test_run_id": "run-1"})
    assert "run-1" not in manager._outbox


@pytest.mark.asyncio
async def test_result_sent_before_registration_is_resent_after_it(manager):
    """Finding 1: the backend could not accept it yet, so it sent no ack."""
    await _registered(manager)
    conn = manager._connection
    conn.drop()
    conn.reconnect()  # new socket, registration not processed yet
    await manager._send_test_result("run-1", status="success", output="x")
    assert _run_ids(conn.sent) == ["run-1"]

    await _registered(manager)

    assert _run_ids(conn.sent) == ["run-1", "run-1"]
    assert "run-1" in manager._outbox  # still waiting for its ack


@pytest.mark.asyncio
async def test_unacked_result_on_a_half_open_socket_is_resent(manager):
    """Finding 7: the socket took the frame, but the backend never saw it."""
    await _registered(manager)
    with patch("rhesis.sdk.connector.outbox.time.monotonic", return_value=1000.0):
        await manager._send_test_result("run-1", status="success")
    later = 1000.0 + ResultOutbox.RESEND_AFTER_SECONDS
    with patch("rhesis.sdk.connector.outbox.time.monotonic", return_value=later):
        await manager._outbox.flush()
    assert _run_ids(manager._connection.sent) == ["run-1", "run-1"]


@pytest.mark.asyncio
async def test_resend_loop_resends_while_registered(manager):
    await _registered(manager)
    manager._connection.drop()
    await manager._send_test_result("run-1", status="success")
    manager._connection.up = True
    manager._connection.state = ConnectionState.CONNECTED

    with patch.object(ConnectorManager, "RESEND_CHECK_SECONDS", 0.01):
        manager._resend_task.cancel()
        manager._resend_task = manager._spawn(manager._resend_loop())
        await asyncio.sleep(0.05)

    assert _run_ids(manager._connection.sent) == ["run-1"]


@pytest.mark.asyncio
async def test_flush_is_paced_below_the_backend_rate_limit():
    """Finding 2: 500 frames/s over the limit are dropped by the backend, silently."""
    sent = []

    async def send(message):
        sent.append(message)

    outbox = ResultOutbox(send)
    outbox.acks = True
    for i in range(120):
        outbox._add(f"run-{i}", {"test_run_id": f"run-{i}"})

    pauses = []

    async def record_pause(seconds):
        pauses.append(seconds)

    with patch.object(outbox_module.asyncio, "sleep", record_pause):
        await outbox.flush(resend_all=True)

    assert len(sent) == 120
    assert pauses == [ResultOutbox.BATCH_PAUSE_SECONDS] * 2
    assert ResultOutbox.BATCH_SIZE / ResultOutbox.BATCH_PAUSE_SECONDS <= 250


# --- Failures ---


@pytest.mark.asyncio
async def test_unserializable_result_is_dropped_and_does_not_block_others(caplog):
    """Finding 3: a non-connection error is not retried, and the flush moves on."""
    sent = []

    async def send(message):
        if message.get("bad"):
            raise TypeError("Object of type object is not JSON serializable")
        sent.append(message)

    outbox = ResultOutbox(send)
    outbox._add("run-1", {"test_run_id": "run-1", "bad": True})
    outbox._add("run-2", {"test_run_id": "run-2"})

    with caplog.at_level("ERROR"):
        await outbox.flush()

    assert _run_ids(sent) == ["run-2"]
    assert len(outbox) == 0
    assert "Dropped result for run run-1" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [ConnectionClosedError(None, None), OSError("reset"), RuntimeError("WebSocket not connected")],
    ids=["closed", "oserror", "not-connected"],
)
async def test_connection_errors_keep_the_result(error):
    async def send(message):
        raise error

    outbox = ResultOutbox(send)
    assert not await outbox.send({"test_run_id": "run-1"})
    assert "run-1" in outbox


@pytest.mark.asyncio
async def test_eviction_during_a_flush_drops_only_the_oldest(caplog):
    """Finding 8: a send that evicts must not make the flush drop another result."""
    sent = []
    outbox: ResultOutbox

    async def send(message):
        sent.append(message["test_run_id"])
        if message["test_run_id"] == "run-1":
            await outbox.send({"test_run_id": "run-new"})  # full: evicts run-1

    outbox = ResultOutbox(send)
    outbox.acks = True
    with patch.object(ResultOutbox, "MAX_SIZE", 3):
        for run_id in ("run-1", "run-2", "run-3"):
            outbox._add(run_id, {"test_run_id": run_id})
        with caplog.at_level("WARNING"):
            await outbox.flush()

    assert sent == ["run-1", "run-new", "run-2", "run-3"]
    assert list(outbox._entries) == ["run-2", "run-3", "run-new"]
    assert "dropped the oldest result (run run-1)" in caplog.text
    assert "run-2)" not in caplog.text


# --- Without acks (older backend) ---


@pytest.mark.asyncio
async def test_without_acks_a_result_is_sent_once(manager):
    await _registered(manager, acks=False)
    await manager._send_test_result("run-1", status="success")
    assert len(manager._outbox) == 0

    await _registered(manager, acks=False)
    assert _run_ids(manager._connection.sent) == ["run-1"]


@pytest.mark.asyncio
async def test_without_acks_a_result_unsent_while_down_goes_after_registering(manager):
    await _registered(manager, acks=False)
    conn = manager._connection
    conn.drop()
    await manager._send_test_result("run-1", status="success", output="late")
    await manager._send_metric_result("metric-1", status="success", score=1.0)
    assert conn.sent == []

    conn.reconnect()
    await _registered(manager, acks=False)

    assert _run_ids(conn.sent) == ["run-1", "metric-1"]
    assert len(manager._outbox) == 0


# --- Second review ---


@pytest.mark.asyncio
async def test_timed_resends_back_off():
    """Item 3: 30s, then 60s, then 120s, capped, so a slow-to-ack backlog does not snowball."""
    sent = []

    async def send(message):
        sent.append(message)

    outbox = ResultOutbox(send)
    outbox.acks = True
    clock = "rhesis.sdk.connector.outbox.time.monotonic"
    with patch(clock, return_value=1000.0):
        await outbox.send({"test_run_id": "run-1"})
    for now, expected in ((1030.0, 2), (1059.0, 2), (1090.0, 3), (1209.0, 3), (1210.0, 4)):
        with patch(clock, return_value=now):
            await outbox.flush()
        assert len(sent) == expected, now

    outbox._entries["run-1"].attempts = 20
    with patch(clock, return_value=1210.0 + ResultOutbox.MAX_RESEND_AFTER_SECONDS):
        await outbox.flush()
    assert len(sent) == 5


@pytest.mark.asyncio
async def test_reregistering_on_the_same_socket_does_not_resend_everything(manager):
    """Item 7: a `registered` reply for a newly decorated function is not a reconnect."""
    await _registered(manager)
    await manager._send_test_result("run-1", status="success")

    await _registered(manager)  # same socket
    assert _run_ids(manager._connection.sent) == ["run-1"]

    manager._connection.reconnect()
    await _registered(manager)
    assert _run_ids(manager._connection.sent) == ["run-1", "run-1"]


# --- Bounds ---


@pytest.mark.asyncio
async def test_full_outbox_drops_the_oldest_with_a_log(manager, caplog):
    manager._connection.drop()
    with (
        patch.object(ResultOutbox, "MAX_SIZE", 2),
        caplog.at_level("WARNING"),
    ):
        for run_id in ("run-1", "run-2", "run-3"):
            await manager._send_test_result(run_id, status="success")

    assert list(manager._outbox._entries) == ["run-2", "run-3"]
    assert "dropped the oldest result (run run-1)" in caplog.text


@pytest.mark.asyncio
async def test_results_older_than_the_age_bound_are_dropped(manager, caplog):
    manager._connection.drop()
    with patch("rhesis.sdk.connector.outbox.time.monotonic", return_value=1000.0):
        await manager._send_test_result("run-old", status="success")

    manager._connection.reconnect()
    later = 1000.0 + ResultOutbox.MAX_AGE_SECONDS + 1
    with (
        patch("rhesis.sdk.connector.outbox.time.monotonic", return_value=later),
        caplog.at_level("WARNING"),
    ):
        await manager._outbox.flush()

    assert manager._connection.sent == []
    assert "Dropped result for run run-old" in caplog.text
