"""Tests for SP11 — WebSocket channel authorization with PDP integration.

Key guarantees tested:

- Resource channel subscription calls authorize() via PDP when a DB session is provided.
- A caller with no org membership is denied for resource channels (deny-first).
- Org member is allowed for resource channels in community tier (org-scoped read).
- Legacy path (db=None) preserves the old allow-any-authenticated behavior.
- User-scoped channels still enforce own-user check.
- Org-scoped channels still enforce own-org check.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/services/websocket/test_sp11_channel_authz.py -v
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from rhesis.backend.app.services.websocket.authorization import ChannelAuthorizer

# ---------------------------------------------------------------------------
# Minimal fake User object (avoids needing a DB row)
# ---------------------------------------------------------------------------


def _fake_user(user_id=None, org_id=None) -> object:
    uid = user_id or uuid.uuid4()
    oid = org_id or uuid.uuid4()
    return SimpleNamespace(id=uid, organization_id=oid)


# ---------------------------------------------------------------------------
# Unit tests — no DB needed for most cases
# ---------------------------------------------------------------------------


class TestChannelAuthorizerUnit:
    @pytest.fixture
    def authorizer(self):
        return ChannelAuthorizer()

    # --- user-scoped channels ---

    @pytest.mark.asyncio
    async def test_user_channel_own_allowed(self, authorizer):
        user_id = uuid.uuid4()
        user = _fake_user(user_id=user_id)
        ok, err = await authorizer.authorize(user, f"user:{user_id}")
        assert ok is True
        assert err is None

    @pytest.mark.asyncio
    async def test_user_channel_other_denied(self, authorizer):
        user = _fake_user()
        other_id = uuid.uuid4()
        ok, err = await authorizer.authorize(user, f"user:{other_id}")
        assert ok is False

    # --- org-scoped channels ---

    @pytest.mark.asyncio
    async def test_org_channel_own_allowed(self, authorizer):
        org_id = uuid.uuid4()
        user = _fake_user(org_id=org_id)
        ok, err = await authorizer.authorize(user, f"org:{org_id}")
        assert ok is True

    @pytest.mark.asyncio
    async def test_org_channel_other_denied(self, authorizer):
        user = _fake_user()
        other_org = uuid.uuid4()
        ok, err = await authorizer.authorize(user, f"org:{other_org}")
        assert ok is False

    # --- resource channels: legacy path (db=None) ---

    @pytest.mark.asyncio
    async def test_resource_channel_no_db_allowed(self, authorizer):
        """Without DB, any authenticated user is allowed (legacy behavior)."""
        user = _fake_user()
        run_id = uuid.uuid4()
        ok, err = await authorizer.authorize(user, f"test_run:{run_id}")
        assert ok is True

    # --- resource channels: PDP path (db provided) ---

    @pytest.mark.asyncio
    async def test_resource_channel_with_db_calls_authorize(self, authorizer):
        """With DB, authorize() is called for resource channels."""
        user = _fake_user()
        run_id = uuid.uuid4()
        fake_db = object()

        # authorize/resolve_principal are imported lazily inside the method,
        # so patch them at their source modules.
        with (
            patch(
                "rhesis.backend.app.auth.rbac.authorize",
                return_value=True,
            ) as mock_authz,
            patch(
                "rhesis.backend.app.auth.principal.resolve_principal",
                return_value=SimpleNamespace(user_id=user.id, organization_id=user.organization_id),
            ),
        ):
            ok, err = await authorizer.authorize(user, f"test_run:{run_id}", db=fake_db)

        assert ok is True
        mock_authz.assert_called_once()
        call_kwargs = mock_authz.call_args
        assert call_kwargs.kwargs["db"] is fake_db
        # capability should be test_run:read
        assert "test_run:read" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_resource_channel_with_db_deny_when_no_permission(self, authorizer):
        """PDP denial for resource channel results in subscription rejected (deny-first)."""
        user = _fake_user()
        run_id = uuid.uuid4()
        fake_db = object()

        with (
            patch(
                "rhesis.backend.app.auth.rbac.authorize",
                return_value=False,
            ),
            patch(
                "rhesis.backend.app.auth.principal.resolve_principal",
                return_value=SimpleNamespace(user_id=user.id, organization_id=user.organization_id),
            ),
        ):
            ok, err = await authorizer.authorize(user, f"test_run:{run_id}", db=fake_db)

        assert ok is False
        assert err is not None

    # --- invalid channel formats ---

    @pytest.mark.asyncio
    async def test_empty_channel_denied(self, authorizer):
        user = _fake_user()
        ok, err = await authorizer.authorize(user, "")
        assert ok is False

    @pytest.mark.asyncio
    async def test_unknown_prefix_denied(self, authorizer):
        user = _fake_user()
        unknown_id = uuid.uuid4()
        ok, err = await authorizer.authorize(user, f"unknown_resource:{unknown_id}")
        assert ok is False

    @pytest.mark.asyncio
    async def test_invalid_uuid_denied(self, authorizer):
        user = _fake_user()
        ok, err = await authorizer.authorize(user, "test_run:not-a-uuid")
        assert ok is False


# ---------------------------------------------------------------------------
# Integration: community provider — resource channel subscription
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestChannelAuthorizerIntegration:
    def _create_org(self, db) -> uuid.UUID:
        from sqlalchemy import text

        org_id = uuid.uuid4()
        db.execute(
            text("INSERT INTO organization (id, name, is_active) VALUES (:id, :name, true)"),
            {"id": str(org_id), "name": f"WSOrg-{org_id.hex[:8]}"},
        )
        db.flush()
        return org_id

    def _create_user(self, db, org_id: uuid.UUID) -> uuid.UUID:
        from sqlalchemy import text

        user_id = uuid.uuid4()
        db.execute(
            text(
                'INSERT INTO "user" (id, email, organization_id, is_active) '
                "VALUES (:id, :email, :oid, true)"
            ),
            {
                "id": str(user_id),
                "email": f"u-{user_id.hex[:8]}@ws.example",
                "oid": str(org_id),
            },
        )
        db.flush()
        return user_id

    def _set_owner(self, db, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
        from sqlalchemy import text

        db.execute(
            text("UPDATE organization SET owner_id = :owner WHERE id = :id"),
            {"owner": str(user_id), "id": str(org_id)},
        )
        db.flush()

    def _point_session(self, db, org_id: uuid.UUID) -> None:
        from sqlalchemy import text

        db.execute(text('SET "app.current_organization" = :o'), {"o": str(org_id)})

    @pytest.mark.asyncio
    async def test_org_owner_allowed_for_resource_channel(self, test_db):
        """Org owner is authorized to subscribe to a resource channel in community tier."""
        db = test_db
        org_id = self._create_org(db)
        user_id = self._create_user(db, org_id)
        self._set_owner(db, org_id, user_id)
        self._point_session(db, org_id)

        user = _fake_user(user_id=user_id, org_id=org_id)
        run_id = uuid.uuid4()

        authorizer = ChannelAuthorizer()
        ok, err = await authorizer.authorize(user, f"test_run:{run_id}", db=db)

        assert ok is True, f"Org owner should be allowed; err={err}"
