"""The server pings quiet connector sockets so the idle timeout does not close them."""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import WebSocketDisconnect

from rhesis.backend.app.routers import connector as connector_router
from rhesis.backend.app.services.connector.schemas import WebSocketConnectionContext


class _PingAnsweringSocket:
    """A client that answers each server ping with a pong, like the SDK does."""

    def __init__(self, answers=True):
        self.answers = answers
        self.inbox: asyncio.Queue = asyncio.Queue()
        self.sent = []
        self.closed_with = None

    async def send_json(self, payload):
        self.sent.append(payload)
        if self.answers and payload.get("type") == "ping":
            await self.inbox.put(json.dumps({"type": "pong"}))

    async def receive_text(self):
        return await self.inbox.get()

    async def close(self, **kwargs):
        self.closed_with = kwargs


@pytest.mark.asyncio
async def test_ping_is_sent_on_the_interval_and_stops_when_cancelled():
    socket = _PingAnsweringSocket(answers=False)
    with patch.object(connector_router, "PING_INTERVAL", 0.01):
        task = asyncio.create_task(connector_router._send_pings(socket, "conn-a"))
        await asyncio.sleep(0.05)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        sent = len(socket.sent)
        await asyncio.sleep(0.03)

    assert sent >= 2
    assert all(m == {"type": "ping"} for m in socket.sent)
    assert len(socket.sent) == sent


@pytest.mark.asyncio
async def test_ping_stops_when_the_socket_is_gone():
    socket = Mock()
    socket.send_json = AsyncMock(side_effect=WebSocketDisconnect())
    with patch.object(connector_router, "PING_INTERVAL", 0.01):
        await asyncio.wait_for(connector_router._send_pings(socket, "conn-a"), timeout=1)
    socket.send_json.assert_awaited_once()


def test_ping_interval_is_well_inside_the_idle_timeout():
    assert connector_router.PING_INTERVAL <= connector_router.IDLE_TIMEOUT / 2


async def _run_loop_with_pings(socket, seconds):
    context = WebSocketConnectionContext(user_id="user-1", organization_id="org-1")
    with (
        patch.object(connector_router, "IDLE_TIMEOUT", 0.2),
        patch.object(connector_router, "PING_INTERVAL", 0.05),
        patch.object(
            connector_router.connection_manager, "handle_message", AsyncMock(return_value=None)
        ),
    ):
        pinger = asyncio.create_task(connector_router._send_pings(socket, "conn-a"))
        loop = asyncio.create_task(connector_router._message_loop(socket, context))
        await asyncio.wait({loop}, timeout=seconds)
        pinger.cancel()
        still_open = not loop.done()
        loop.cancel()
        await asyncio.gather(pinger, loop, return_exceptions=True)
    return still_open


@pytest.mark.asyncio
async def test_a_connection_that_answers_pings_outlives_the_idle_timeout():
    socket = _PingAnsweringSocket(answers=True)
    assert await _run_loop_with_pings(socket, seconds=0.6)
    assert socket.closed_with is None


@pytest.mark.asyncio
async def test_a_connection_that_stops_answering_is_still_closed():
    socket = _PingAnsweringSocket(answers=False)
    assert not await _run_loop_with_pings(socket, seconds=0.6)
    assert socket.closed_with == {"code": 1000, "reason": "Idle timeout"}
