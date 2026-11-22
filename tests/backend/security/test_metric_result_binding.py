"""An SDK ``metric_result`` is accepted only from the connection it was dispatched to."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from rhesis.backend.app.services.connector.manager import ConnectionManager


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
    async def test_disconnect_drops_the_binding(self, manager):
        await manager.send_metric_by_connection("conn-a", "run-2", "m", {})
        with patch.object(manager, "_track_background_task"):
            manager.disconnect_by_connection_id("conn-a")
        assert "run-2" not in manager._pending_metric_connections
