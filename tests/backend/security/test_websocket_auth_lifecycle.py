"""Open WebSockets re-evaluate their authorization while connected.

Two follow-ups to the membership re-check:

- The credential that opened a socket is re-checked, so a logged-out session or a
  revoked API token drops its open socket instead of living on (PR 26).
- The channels a socket already subscribed to are re-evaluated, so a role change
  inside the org drops a channel the user can no longer access (PR 27).
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from rhesis.backend.app.auth.principal import AuthKind, resolve_principal
from rhesis.backend.app.schemas.websocket import EventType
from rhesis.backend.app.services.websocket import membership
from rhesis.backend.app.services.websocket.credential_liveness import (
    SocketCredential,
    credential_from_bearer,
    credential_is_current,
)
from rhesis.backend.app.services.websocket.manager import WebSocketManager

MEMBERSHIP = "rhesis.backend.app.services.websocket.membership"
LIVENESS = "rhesis.backend.app.services.websocket.credential_liveness"


@pytest.mark.security
class TestCredentialLiveness:
    @pytest.mark.asyncio
    async def test_logged_out_session_is_not_current(self):
        cred = SocketCredential(user_id="u", session_issued_at=1000)
        with patch(f"{LIVENESS}.is_session_revoked", AsyncMock(return_value=True)):
            assert not await credential_is_current(cred)

    @pytest.mark.asyncio
    async def test_live_session_is_current(self):
        cred = SocketCredential(user_id="u", session_issued_at=1000)
        with patch(f"{LIVENESS}.is_session_revoked", AsyncMock(return_value=False)):
            assert await credential_is_current(cred)

    @pytest.mark.asyncio
    async def test_revoked_api_token_is_not_current(self):
        cred = SocketCredential(user_id="u", api_token_value="rh-dead")
        with patch(f"{LIVENESS}._api_token_valid", return_value=False):
            assert not await credential_is_current(cred)

    @pytest.mark.asyncio
    async def test_live_api_token_is_current(self):
        cred = SocketCredential(user_id="u", api_token_value="rh-live")
        with patch(f"{LIVENESS}._api_token_valid", return_value=True):
            assert await credential_is_current(cred)

    @pytest.mark.asyncio
    async def test_credential_without_fields_is_current(self):
        # A stateless M2M JWT carries nothing to re-check; its own expiry bounds it.
        assert await credential_is_current(SocketCredential(user_id="u"))

    @pytest.mark.asyncio
    async def test_backend_error_keeps_the_socket(self):
        cred = SocketCredential(user_id="u", session_issued_at=1000)
        with patch(f"{LIVENESS}.is_session_revoked", AsyncMock(side_effect=RuntimeError("down"))):
            assert await credential_is_current(cred)


@pytest.mark.security
class TestCredentialFromBearer:
    def test_api_token_binds_to_its_value(self):
        cred = credential_from_bearer("rh-abc", "u", is_session=False)
        assert cred.api_token_value == "rh-abc"
        assert cred.session_issued_at is None

    def test_session_jwt_binds_to_its_issue_time(self):
        with (
            patch(
                "rhesis.backend.app.auth.token_utils.verify_jwt_token",
                return_value={"iat": 1234},
            ),
            patch("rhesis.backend.app.auth.user_utils.get_secret_key", return_value="k"),
        ):
            cred = credential_from_bearer("jwt-token", "u", is_session=True)
        assert cred.session_issued_at == 1234
        assert cred.api_token_value is None

    def test_m2m_jwt_binds_nothing(self):
        cred = credential_from_bearer("jwt-token", "u", is_session=False)
        assert cred.session_issued_at is None
        assert cred.api_token_value is None


@pytest.mark.security
class TestWatcherClosesOnRevocation:
    @pytest.mark.asyncio
    async def test_watcher_closes_when_credential_revoked(self):
        websocket = AsyncMock()
        on_close = Mock()
        cred = SocketCredential(user_id="u", session_issued_at=1000)
        with (
            patch(f"{MEMBERSHIP}.MEMBERSHIP_CHECK_INTERVAL_SECONDS", 0),
            patch(f"{MEMBERSHIP}.membership_is_current", AsyncMock(return_value=True)),
            patch(f"{MEMBERSHIP}.credential_is_current", AsyncMock(side_effect=[True, False])),
        ):
            await asyncio.wait_for(
                membership.watch_membership(websocket, "u", "o", on_close, credential=cred),
                timeout=2,
            )
        on_close.assert_called_once()
        websocket.close.assert_awaited_once_with(
            code=membership.MEMBERSHIP_CLOSE_CODE, reason=membership.AUTH_CLOSE_REASON
        )

    @pytest.mark.asyncio
    async def test_membership_still_takes_priority(self):
        websocket = AsyncMock()
        cred = SocketCredential(user_id="u", session_issued_at=1000)
        with (
            patch(f"{MEMBERSHIP}.MEMBERSHIP_CHECK_INTERVAL_SECONDS", 0),
            patch(f"{MEMBERSHIP}.membership_is_current", AsyncMock(return_value=False)),
            patch(f"{MEMBERSHIP}.credential_is_current", AsyncMock(return_value=True)),
        ):
            await asyncio.wait_for(
                membership.watch_membership(websocket, "u", "o", Mock(), credential=cred),
                timeout=2,
            )
        websocket.close.assert_awaited_once_with(
            code=membership.MEMBERSHIP_CLOSE_CODE, reason=membership.MEMBERSHIP_CLOSE_REASON
        )


@pytest.mark.security
class TestFrontendSocketCredential:
    @pytest.fixture
    def ws_manager(self):
        with patch("rhesis.backend.app.routers.websocket.ws_manager") as mgr:
            mgr.connect = AsyncMock(return_value="ws_lifecycle")
            mgr.disconnect = Mock()
            mgr.handle_message = AsyncMock()
            mgr.register_principal = Mock()
            mgr.revalidate_subscriptions = AsyncMock()
            yield mgr

    @pytest.fixture
    def user(self, make_ws_user):
        user = make_ws_user()
        cred = SocketCredential(user_id=str(user.id), session_issued_at=1000)
        with patch(
            "rhesis.backend.app.routers.websocket.authenticate_websocket_token",
            AsyncMock(return_value=(user, resolve_principal(user), cred)),
        ):
            yield user

    def test_message_on_a_revoked_credential_closes_the_socket(
        self, authenticated_client: TestClient, ws_manager, user
    ):
        # Membership is fine; only the credential (logout / token revoke) ended.
        with (
            patch(f"{MEMBERSHIP}.membership_is_current", AsyncMock(return_value=True)),
            patch(f"{MEMBERSHIP}.credential_is_current", AsyncMock(return_value=False)),
        ):
            with authenticated_client.websocket_connect("/ws?token=t") as ws:
                assert ws.receive_json()["type"] == EventType.CONNECTED.value
                ws.send_json({"type": "subscribe", "payload": {"channel": f"user:{user.id}"}})
                with pytest.raises(WebSocketDisconnect) as closed:
                    ws.receive_json()
        assert closed.value.code == membership.MEMBERSHIP_CLOSE_CODE
        ws_manager.handle_message.assert_not_awaited()
        ws_manager.disconnect.assert_called_with("ws_lifecycle")


@pytest.mark.security
class TestConnectorSocketCredential:
    def test_sdk_socket_closes_when_credential_revoked(
        self, authenticated_client: TestClient, make_ws_user
    ):
        user = make_ws_user()
        principal = Mock(token_project_id=None, kind=AuthKind.TOKEN)
        with (
            patch(
                "rhesis.backend.app.routers.connector.authenticate_websocket",
                AsyncMock(return_value=(user, principal)),
            ),
            patch("rhesis.backend.app.routers.connector.connection_manager") as mgr,
            patch(f"{MEMBERSHIP}.MEMBERSHIP_CHECK_INTERVAL_SECONDS", 0.01),
            patch(f"{MEMBERSHIP}.membership_is_current", AsyncMock(return_value=True)),
            patch(f"{MEMBERSHIP}.credential_is_current", AsyncMock(return_value=False)),
        ):
            mgr.connect = AsyncMock()
            mgr.disconnect_by_connection_id = Mock()
            with authenticated_client.websocket_connect(
                "/connector/ws", headers={"Authorization": "Bearer rh-token"}
            ) as ws:
                assert ws.receive_json()["type"] == "connected"
                with pytest.raises(WebSocketDisconnect) as closed:
                    ws.receive_json()
        assert closed.value.code == membership.MEMBERSHIP_CLOSE_CODE
        mgr.disconnect_by_connection_id.assert_called()


@pytest.mark.security
class TestChannelRevalidation:
    """A role change re-runs channel authorization on the open socket (PR 27)."""

    def _manager_with_subscription(self, channel: str):
        mgr = WebSocketManager()
        conn_id = "ws_reval"
        websocket = AsyncMock()
        mgr._registry.add(conn_id, websocket, user_id="u", org_id="o")
        mgr._registry.add_subscription(conn_id, channel)
        mgr._principals[conn_id] = Mock()
        mgr._subscription_project_hints[conn_id] = {channel: ""}
        return mgr, conn_id, websocket

    @pytest.mark.asyncio
    async def test_channel_lost_on_role_change_is_dropped(self):
        channel = f"test_run:{uuid.uuid4()}"
        mgr, conn_id, websocket = self._manager_with_subscription(channel)
        user = Mock(id="u", organization_id="o")

        authorizer = Mock()
        authorizer.PROTECTED_RESOURCE_PREFIXES = ["test_run:"]
        authorizer.authorize_sync = Mock(return_value=(False, "denied"))
        with (
            patch(
                "rhesis.backend.app.services.websocket.manager.get_channel_authorizer",
                return_value=authorizer,
            ),
            patch("rhesis.backend.app.database.get_db_with_tenant_variables"),
        ):
            await mgr.revalidate_subscriptions(conn_id, user)

        assert channel not in mgr.get_subscriptions(conn_id)
        assert channel not in mgr._subscription_project_hints.get(conn_id, {})
        sent = websocket.send_json.await_args[0][0]
        assert sent["type"] == EventType.SUBSCRIPTION_ERROR.value

    @pytest.mark.asyncio
    async def test_still_authorized_channel_is_kept(self):
        channel = f"test_run:{uuid.uuid4()}"
        mgr, conn_id, websocket = self._manager_with_subscription(channel)
        user = Mock(id="u", organization_id="o")

        authorizer = Mock()
        authorizer.PROTECTED_RESOURCE_PREFIXES = ["test_run:"]
        authorizer.authorize_sync = Mock(return_value=(True, None))
        with (
            patch(
                "rhesis.backend.app.services.websocket.manager.get_channel_authorizer",
                return_value=authorizer,
            ),
            patch("rhesis.backend.app.database.get_db_with_tenant_variables"),
        ):
            await mgr.revalidate_subscriptions(conn_id, user)

        assert channel in mgr.get_subscriptions(conn_id)
        websocket.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_user_channel_is_not_re_evaluated(self):
        # Only PDP-checked resource channels are re-evaluated; user:/org: are not.
        channel = f"user:{uuid.uuid4()}"
        mgr, conn_id, websocket = self._manager_with_subscription(channel)
        user = Mock(id="u", organization_id="o")

        authorizer = Mock()
        authorizer.PROTECTED_RESOURCE_PREFIXES = ["test_run:"]
        authorizer.authorize_sync = Mock(return_value=(False, "denied"))
        with patch(
            "rhesis.backend.app.services.websocket.manager.get_channel_authorizer",
            return_value=authorizer,
        ):
            await mgr.revalidate_subscriptions(conn_id, user)

        assert channel in mgr.get_subscriptions(conn_id)
        authorizer.authorize_sync.assert_not_called()
