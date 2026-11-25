"""Open WebSockets close once their user leaves the organization they connected with.

Covers the frontend ``/ws`` and the SDK ``/connector/ws`` sockets, for a user who left,
was removed from, or was deactivated in the organization.
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from rhesis.backend.app import models
from rhesis.backend.app.auth.constants import AuthProviderType
from rhesis.backend.app.auth.principal import resolve_principal
from rhesis.backend.app.crud import user as user_crud
from rhesis.backend.app.schemas import UserCreate
from rhesis.backend.app.schemas.websocket import EventType
from rhesis.backend.app.services.websocket import membership
from rhesis.backend.app.services.websocket.credential_liveness import SocketCredential

MEMBERSHIP = "rhesis.backend.app.services.websocket.membership"


def _user(db: Session, org_id: str) -> models.User:
    user = user_crud.create_user(
        db,
        UserCreate(
            email=f"ws-tenant-{uuid.uuid4().hex[:10]}@example.com",
            provider_type=AuthProviderType.GOOGLE,
            is_active=True,
            is_email_verified=True,
            organization_id=uuid.UUID(org_id),
        ),
    )
    db.flush()
    return user


@pytest.mark.security
class TestMembershipCheck:
    def test_member_of_the_connected_org_is_current(self, test_db: Session, test_org_id: str):
        user = _user(test_db, test_org_id)
        assert membership._is_member(str(user.id), test_org_id)

    def test_user_who_left_the_org_is_not_current(self, test_db: Session, test_org_id: str):
        user = _user(test_db, test_org_id)
        user.organization_id = None
        test_db.flush()
        assert not membership._is_member(str(user.id), test_org_id)

    def test_user_now_in_another_org_is_not_current(self, test_db: Session, test_org_id: str):
        user = _user(test_db, test_org_id)
        assert not membership._is_member(str(user.id), str(uuid.uuid4()))

    def test_deactivated_user_is_not_current(self, test_db: Session, test_org_id: str):
        user = _user(test_db, test_org_id)
        user.is_active = False
        test_db.flush()
        assert not membership._is_member(str(user.id), test_org_id)

    @pytest.mark.asyncio
    async def test_lookup_failure_keeps_the_socket(self):
        with patch(f"{MEMBERSHIP}._is_member", side_effect=RuntimeError("db down")):
            assert await membership.membership_is_current("u", "o")

    @pytest.mark.asyncio
    async def test_watcher_drops_and_closes_when_membership_ends(self):
        websocket = AsyncMock()
        on_close = Mock()
        with (
            patch(f"{MEMBERSHIP}.MEMBERSHIP_CHECK_INTERVAL_SECONDS", 0),
            patch(
                f"{MEMBERSHIP}.membership_is_current", AsyncMock(side_effect=[True, True, False])
            ),
        ):
            await asyncio.wait_for(
                membership.watch_membership(websocket, "u", "o", on_close=on_close),
                timeout=2,
            )
        on_close.assert_called_once()
        websocket.close.assert_awaited_once_with(
            code=membership.MEMBERSHIP_CLOSE_CODE, reason=membership.MEMBERSHIP_CLOSE_REASON
        )

    @pytest.mark.asyncio
    async def test_watcher_leaves_a_current_member_connected(self):
        websocket = AsyncMock()
        on_close = Mock()
        with (
            patch(f"{MEMBERSHIP}.MEMBERSHIP_CHECK_INTERVAL_SECONDS", 0),
            patch(f"{MEMBERSHIP}.membership_is_current", AsyncMock(return_value=True)),
        ):
            watch = asyncio.create_task(
                membership.watch_membership(websocket, "u", "o", on_close=on_close)
            )
            await asyncio.sleep(0.05)
            watch.cancel()
        websocket.close.assert_not_awaited()
        on_close.assert_not_called()


@pytest.mark.security
class TestMembershipCheckInterval:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("", 30.0), ("45", 45.0), ("0", 1.0), ("-5", 1.0), ("abc", 30.0), ("inf", 30.0)],
    )
    def test_interval_from_env(self, monkeypatch, raw, expected):
        monkeypatch.setenv("WS_MEMBERSHIP_CHECK_INTERVAL", raw)
        assert membership._interval_from_env() == expected


@pytest.mark.security
class TestFrontendSocketMembership:
    @pytest.fixture
    def ws_manager(self):
        with patch("rhesis.backend.app.routers.websocket.ws_manager") as mgr:
            mgr.connect = AsyncMock(return_value="ws_tenant")
            mgr.disconnect = Mock()
            mgr.handle_message = AsyncMock()
            yield mgr

    @pytest.fixture
    def user(self, make_ws_user):
        user = make_ws_user()
        # Bare credential: nothing to re-check, so these tests isolate membership.
        credential = SocketCredential(user_id=str(user.id))
        with patch(
            "rhesis.backend.app.routers.websocket.authenticate_websocket_token",
            AsyncMock(return_value=(user, resolve_principal(user), credential)),
        ):
            yield user

    def test_message_after_leaving_the_org_closes_the_socket(
        self, authenticated_client: TestClient, ws_manager, user
    ):
        with patch(
            f"{MEMBERSHIP}.membership_is_current",
            AsyncMock(return_value=False),
        ):
            with authenticated_client.websocket_connect("/ws?token=t") as ws:
                assert ws.receive_json()["type"] == EventType.CONNECTED.value
                ws.send_json({"type": "subscribe", "payload": {"channel": f"user:{user.id}"}})
                with pytest.raises(WebSocketDisconnect) as closed:
                    ws.receive_json()
        assert closed.value.code == membership.MEMBERSHIP_CLOSE_CODE
        ws_manager.handle_message.assert_not_awaited()
        ws_manager.disconnect.assert_called_with("ws_tenant")

    def test_message_from_a_current_member_is_handled(
        self, authenticated_client: TestClient, ws_manager, user
    ):
        with patch(
            f"{MEMBERSHIP}.membership_is_current",
            AsyncMock(return_value=True),
        ):
            with authenticated_client.websocket_connect("/ws?token=t") as ws:
                ws.receive_json()
                ws.send_json({"type": "subscribe", "payload": {"channel": f"user:{user.id}"}})
                # Messages are handled in order, so this reply means the subscribe ran.
                ws.send_text("not json")
                assert ws.receive_json()["type"] == EventType.ERROR.value
        ws_manager.handle_message.assert_awaited_once()

    def test_idle_socket_is_closed_by_the_watcher(
        self, authenticated_client: TestClient, ws_manager, user
    ):
        with (
            patch(f"{MEMBERSHIP}.MEMBERSHIP_CHECK_INTERVAL_SECONDS", 0.01),
            patch(f"{MEMBERSHIP}.membership_is_current", AsyncMock(return_value=False)),
        ):
            with authenticated_client.websocket_connect("/ws?token=t") as ws:
                ws.receive_json()
                with pytest.raises(WebSocketDisconnect) as closed:
                    ws.receive_json()
        assert closed.value.code == membership.MEMBERSHIP_CLOSE_CODE
        ws_manager.disconnect.assert_called_with("ws_tenant")


@pytest.mark.security
class TestConnectorSocketMembership:
    def test_sdk_socket_is_closed_when_membership_ends(
        self, authenticated_client: TestClient, make_ws_user
    ):
        user = make_ws_user()
        with (
            patch(
                "rhesis.backend.app.routers.connector.authenticate_websocket",
                AsyncMock(return_value=(user, Mock(token_project_id=None))),
            ),
            patch("rhesis.backend.app.routers.connector.connection_manager") as mgr,
            patch(f"{MEMBERSHIP}.MEMBERSHIP_CHECK_INTERVAL_SECONDS", 0.01),
            patch(f"{MEMBERSHIP}.membership_is_current", AsyncMock(return_value=False)),
        ):
            mgr.connect = AsyncMock()
            mgr.disconnect_by_connection_id = Mock()
            with authenticated_client.websocket_connect(
                "/connector/ws", headers={"Authorization": "Bearer t"}
            ) as ws:
                assert ws.receive_json()["type"] == "connected"
                with pytest.raises(WebSocketDisconnect) as closed:
                    ws.receive_json()
        assert closed.value.code == membership.MEMBERSHIP_CLOSE_CODE
        mgr.disconnect_by_connection_id.assert_called()
