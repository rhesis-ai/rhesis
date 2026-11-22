"""A ``preflight:{id}`` channel belongs to the first user who uses the id."""

import asyncio
import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.schemas.websocket import EventType, WebSocketMessage
from rhesis.backend.app.services.websocket import preflight_owner
from rhesis.backend.app.services.websocket.manager import WebSocketManager
from rhesis.backend.app.services.websocket.preflight_owner import claim_preflight_channel
from tests.backend.fixtures.fake_redis import FakeRedis, fake_redis_manager

ORCHESTRATOR = "rhesis.backend.app.routers.preflight.run_preflight_checks_multi"


def _fake_user(org_id=None) -> Mock:
    user = Mock()
    user.id = uuid.uuid4()
    user.organization_id = org_id or uuid.uuid4()
    user.email = "ws-tenant@example.com"
    return user


@pytest.mark.security
class TestPreflightChannelOwner:
    @pytest.fixture(autouse=True)
    def _no_local_owners(self):
        preflight_owner._local_owners.clear()
        yield
        preflight_owner._local_owners.clear()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("redis_up", [True, False])
    async def test_first_user_owns_the_id(self, redis_up):
        correlation_id = str(uuid.uuid4())
        with fake_redis_manager(available=redis_up):
            assert await claim_preflight_channel(correlation_id, "alice")
            assert await claim_preflight_channel(correlation_id, "alice")
            assert not await claim_preflight_channel(correlation_id, "bob")

    @pytest.mark.asyncio
    async def test_claim_survives_the_key_expiring_between_set_and_get(self):
        class ExpiresOnce(FakeRedis):
            async def get(self, key):
                if not getattr(self, "expired", False):
                    self.expired = True
                    self.data.pop(key, None)
                    return None
                return await super().get(key)

        redis = ExpiresOnce()
        correlation_id = str(uuid.uuid4())
        redis.data[f"preflight_owner:{correlation_id}"] = "bob"
        with fake_redis_manager(redis):
            assert await claim_preflight_channel(correlation_id, "alice")
        assert redis.data[f"preflight_owner:{correlation_id}"] == "alice"

    @pytest.mark.asyncio
    async def test_subscribe_to_another_users_preflight_is_denied(self):
        manager = WebSocketManager()
        owner, other = _fake_user(), _fake_user()
        websocket = AsyncMock()
        channel = f"preflight:{uuid.uuid4()}"
        authorizer = Mock(authorize_sync=Mock(return_value=(True, None)))
        with (
            fake_redis_manager(),
            patch(
                "rhesis.backend.app.services.websocket.manager.get_channel_authorizer",
                return_value=authorizer,
            ),
            patch("rhesis.backend.app.database.get_db_with_tenant_variables"),
        ):
            assert await claim_preflight_channel(channel.split(":", 1)[1], str(owner.id))
            conn_id = await manager.connect(websocket, other)
            await manager.handle_message(
                conn_id,
                other,
                WebSocketMessage(type=EventType.SUBSCRIBE, payload={"channel": channel}),
            )

            assert channel not in manager.get_subscriptions(conn_id)
            sent = websocket.send_json.await_args.args[0]
            assert sent["type"] == EventType.SUBSCRIPTION_ERROR.value

            owner_conn = await manager.connect(AsyncMock(), owner)
            await manager.handle_message(
                owner_conn,
                owner,
                WebSocketMessage(type=EventType.SUBSCRIBE, payload={"channel": channel}),
            )
            assert channel in manager.get_subscriptions(owner_conn)

    @pytest.fixture
    def test_sets(self, test_db: Session, test_org_id, authenticated_user_id):
        ts = models.TestSet(
            name=f"Preflight owner {uuid.uuid4().hex[:8]}",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add(ts)
        test_db.commit()
        test_db.refresh(ts)
        return [str(ts.id)]

    @patch(ORCHESTRATOR, new_callable=AsyncMock)
    def test_run_on_another_users_id_is_refused(
        self, mock_run, authenticated_client: TestClient, test_sets
    ):
        mock_run.return_value = []
        correlation_id = str(uuid.uuid4())
        body = {
            "test_set_ids": test_sets,
            "endpoint_id": str(uuid.uuid4()),
            "correlation_id": correlation_id,
        }
        with fake_redis_manager():
            asyncio.run(claim_preflight_channel(correlation_id, str(uuid.uuid4())))
            refused = authenticated_client.post("/preflight-checks", json=body)
            body["correlation_id"] = str(uuid.uuid4())
            accepted = authenticated_client.post("/preflight-checks", json=body)

        assert refused.status_code == status.HTTP_409_CONFLICT
        assert accepted.status_code == status.HTTP_202_ACCEPTED
        assert accepted.json()["correlation_id"] == body["correlation_id"]
