"""SDK results are accepted only from a connection of the scope the call was dispatched to."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from rhesis.backend.app.services.connector.manager import ConnectionManager
from rhesis.backend.app.services.connector.pending import PendingCall
from rhesis.backend.app.services.connector.schemas import WebSocketConnectionContext


def _call(run_id, connection_id):
    """A test call dispatched on *connection_id*, as send_test_request records it."""
    return PendingCall(
        kind="test",
        run_id=run_id,
        connection_id=connection_id,
        worker_id="worker",
        organization_id=None,
        user_id=None,
    )


@pytest.mark.security
class TestMetricResultBinding:
    @pytest.fixture
    def manager(self):
        mgr = ConnectionManager()
        mgr._connections["conn-a"] = AsyncMock()
        mgr._connections["conn-b"] = AsyncMock()
        return mgr

    async def _send_result(self, manager, connection_id, metric_run_id):
        await manager.handle_message(
            connection_id=connection_id,
            message={"type": "metric_result", "metric_run_id": metric_run_id, "score": 1},
            db_factory=Mock(side_effect=AssertionError("no session expected")),
            organization_id=None,
        )

    @pytest.mark.asyncio
    async def test_result_from_another_connection_is_ignored(self, manager):
        with patch.object(manager, "_resolve_metric_result") as resolve:
            await manager.send_metric_by_connection("conn-a", "run-1", "m", {})
            await self._send_result(manager, "conn-b", "run-1")
            resolve.assert_not_called()

            await self._send_result(manager, "conn-a", "run-1")
            resolve.assert_called_once()

    @pytest.mark.asyncio
    async def test_result_for_a_metric_not_dispatched_here_is_ignored(self, manager):
        with patch.object(manager, "_resolve_metric_result") as resolve:
            await self._send_result(manager, "conn-b", "run-from-elsewhere")
        resolve.assert_not_called()

    @pytest.mark.asyncio
    async def test_rpc_dispatched_metric_accepts_only_its_connection(self, manager):
        with (
            patch.object(manager, "_resolve_metric_result") as resolve,
            patch.object(manager, "_publish_error_response", AsyncMock()),
        ):
            await manager._handle_rpc_request(
                {
                    "request_id": "run-rpc",
                    "request_type": "execute_metric",
                    "metric_name": "m",
                    "inputs": {},
                    "connection_id": "conn-a",
                }
            )
            await self._send_result(manager, "conn-b", "run-rpc")
            resolve.assert_not_called()
            await self._send_result(manager, "conn-a", "run-rpc")
            resolve.assert_called_once()

    @pytest.mark.asyncio
    async def test_project_routed_rpc_metric_accepts_only_its_connection(self, manager):
        key = manager.get_connection_key("project-1", "dev")
        manager._project_routing[key] = "conn-a"
        with (
            patch.object(manager, "_resolve_metric_result") as resolve,
            patch.object(manager, "_publish_error_response", AsyncMock()),
        ):
            await manager._handle_rpc_request(
                {
                    "request_id": "run-routed",
                    "request_type": "execute_metric",
                    "metric_name": "m",
                    "inputs": {},
                    "project_id": "project-1",
                    "environment": "dev",
                }
            )
            manager._connections["conn-a"].send_json.assert_awaited_once()
            await self._send_result(manager, "conn-b", "run-routed")
            resolve.assert_not_called()
            await self._send_result(manager, "conn-a", "run-routed")
            resolve.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_keeps_the_call_for_a_reconnect(self, manager):
        await manager.send_metric_by_connection("conn-a", "run-2", "m", {})
        with patch.object(manager, "_track_background_task"):
            manager.disconnect_by_connection_id("conn-a")
        assert "run-2" in manager._pending["metric"]

    @staticmethod
    def _with_connections(*connections):
        manager = ConnectionManager()
        for conn_id, org, user, metric in connections:
            manager._connections[conn_id] = AsyncMock()
            manager._contexts[conn_id] = WebSocketConnectionContext(
                connection_id=conn_id, user_id=user, organization_id=org
            )
            manager._connection_metric_keys[conn_id] = {(org, metric)}
        return manager

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "org, user, metric, accepted",
        [
            ("org-1", "user-1", "m", True),
            ("org-2", "user-1", "m", False),
            ("org-1", "user-1", "other", False),
            ("org-1", "user-2", "m", False),
        ],
        ids=["same-scope", "other-org", "metric-not-registered", "other-user"],
    )
    async def test_metric_only_result_after_reconnect(self, org, user, metric, accepted):
        manager = self._with_connections(
            ("conn-a", "org-1", "user-1", "m"), ("conn-b", org, user, metric)
        )
        await manager.send_metric_by_connection("conn-a", "run-3", "m", {})
        with (
            patch.object(manager, "_track_background_task"),
            patch.object(manager, "_resolve_metric_result") as resolve,
        ):
            manager.disconnect_by_connection_id("conn-a")
            await self._send_result(manager, "conn-b", "run-3")

        assert resolve.called is accepted

    @pytest.mark.asyncio
    async def test_same_scope_connection_cannot_answer_while_dispatcher_is_alive(self):
        """Finding 5: a second SDK in the scope must not inject a score for a live call."""
        manager = self._with_connections(
            ("conn-a", "org-1", "user-1", "m"), ("conn-b", "org-1", "user-1", "m")
        )
        await manager.send_metric_by_connection("conn-a", "run-4", "m", {})
        with patch.object(manager, "_resolve_metric_result") as resolve:
            await self._send_result(manager, "conn-b", "run-4")
            resolve.assert_not_called()
            await self._send_result(manager, "conn-a", "run-4")
        resolve.assert_called_once()


@pytest.mark.security
class TestTestResultBinding:
    @pytest.fixture
    def manager(self):
        mgr = ConnectionManager()
        mgr._connections["conn-a"] = AsyncMock()
        mgr._connections["conn-b"] = AsyncMock()
        return mgr

    async def _send_result(self, manager, connection_id, test_run_id):
        with patch("rhesis.backend.app.services.connector.manager.message_handler") as handler:
            handler.handle_test_result_message = AsyncMock()
            await manager.handle_message(
                connection_id=connection_id,
                message={"type": "test_result", "test_run_id": test_run_id, "status": "success"},
                db_factory=Mock(side_effect=AssertionError("no session expected")),
                organization_id=None,
            )
            return handler.handle_test_result_message

    @pytest.mark.asyncio
    async def test_unbound_result_is_ignored(self, manager):
        with patch.object(manager, "_resolve_test_result") as resolve:
            handled = await self._send_result(manager, "conn-b", "run-from-elsewhere")
        resolve.assert_not_called()
        handled.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_result_from_the_dispatched_connection_is_handled(self, manager):
        manager._pending["test"]["run-1"] = _call("run-1", "conn-a")
        with patch.object(manager, "_resolve_test_result") as resolve:
            handled = await self._send_result(manager, "conn-b", "run-1")
            resolve.assert_not_called()
            handled.assert_not_awaited()
            handled = await self._send_result(manager, "conn-a", "run-1")
        resolve.assert_called_once()
        handled.assert_awaited_once()
