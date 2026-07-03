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

from rhesis.backend.app.auth.principal import resolve_principal
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
    async def test_resource_channel_with_db_calls_authorize_for_project(self, authorizer):
        """With DB, authorize() is called against the resource's resolved project."""
        user = _fake_user()
        run_id = uuid.uuid4()
        project_id = uuid.uuid4()
        fake_db = object()

        # Stub the project resolver (avoids a real DB); authorize is imported
        # lazily inside the method, so patch it at its source. The caller must
        # supply the connection's Principal (the manager always does); a missing
        # principal now fails closed (see test_resource_channel_missing_principal_denied).
        principal = SimpleNamespace(user_id=user.id, organization_id=user.organization_id)
        with (
            patch.object(
                authorizer, "_resolve_channel_project_id", return_value=(project_id, True)
            ),
            patch(
                "rhesis.backend.app.auth.rbac.authorize",
                return_value=True,
            ) as mock_authz,
        ):
            ok, err = await authorizer.authorize(
                user, f"test_run:{run_id}", db=fake_db, principal=principal
            )

        assert ok is True
        mock_authz.assert_called_once()
        call = mock_authz.call_args
        # capability is passed positionally; project_id is the resolved project.
        assert "test_run:read" in str(call)
        assert call.kwargs["project_id"] == project_id
        assert call.kwargs["db"] is fake_db

    @pytest.mark.asyncio
    async def test_resource_channel_with_db_deny_when_no_permission(self, authorizer):
        """PDP denial for resource channel results in subscription rejected (deny-first)."""
        user = _fake_user()
        run_id = uuid.uuid4()
        project_id = uuid.uuid4()
        fake_db = object()

        principal = SimpleNamespace(user_id=user.id, organization_id=user.organization_id)
        with (
            patch.object(
                authorizer, "_resolve_channel_project_id", return_value=(project_id, True)
            ),
            patch(
                "rhesis.backend.app.auth.rbac.authorize",
                return_value=False,
            ),
        ):
            ok, err = await authorizer.authorize(
                user, f"test_run:{run_id}", db=fake_db, principal=principal
            )

        assert ok is False
        assert err is not None

    @pytest.mark.asyncio
    async def test_resource_channel_not_found_denied(self, authorizer):
        """A persisted resource not visible in the caller's org is denied (fail-closed).

        authorize() must NOT be called — the resource never resolved.
        """
        user = _fake_user()
        run_id = uuid.uuid4()
        fake_db = object()

        principal = SimpleNamespace(user_id=user.id, organization_id=user.organization_id)
        with (
            patch.object(authorizer, "_resolve_channel_project_id", return_value=(None, False)),
            patch("rhesis.backend.app.auth.rbac.authorize", return_value=True) as mock_authz,
        ):
            ok, err = await authorizer.authorize(
                user, f"test_run:{run_id}", db=fake_db, principal=principal
            )

        assert ok is False
        assert err is not None
        mock_authz.assert_not_called()

    @pytest.mark.asyncio
    async def test_preflight_channel_ephemeral_no_project_lookup(self, authorizer):
        """preflight: channels are ephemeral — authorized org-scoped, no resource lookup."""
        user = _fake_user()
        corr_id = uuid.uuid4()
        fake_db = object()

        principal = SimpleNamespace(user_id=user.id, organization_id=user.organization_id)
        with (
            patch("rhesis.backend.app.auth.rbac.authorize", return_value=True) as mock_authz,
        ):
            ok, err = await authorizer.authorize(
                user, f"preflight:{corr_id}", db=fake_db, principal=principal
            )

        assert ok is True
        call = mock_authz.call_args
        # Ephemeral: org-scoped (project_id=None), capability preflight:create.
        assert call.kwargs["project_id"] is None
        assert "preflight:create" in str(call)

    @pytest.mark.asyncio
    async def test_resource_channel_missing_principal_denied(self, authorizer):
        """Fail closed: on the PDP path, a missing Principal is denied rather than
        synthesised from `user` (which would drop the token's SP9 scopes)."""
        user = _fake_user()
        run_id = uuid.uuid4()
        fake_db = object()

        with (
            patch.object(
                authorizer, "_resolve_channel_project_id", return_value=(uuid.uuid4(), True)
            ),
            patch("rhesis.backend.app.auth.rbac.authorize", return_value=True) as mock_authz,
        ):
            ok, err = await authorizer.authorize(
                user, f"test_run:{run_id}", db=fake_db, principal=None
            )

        assert ok is False
        assert err is not None
        mock_authz.assert_not_called()

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

    def _assign_owner_role(self, db, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Give the user the built-in Owner org role.

        Under RBAC, project-channel access for an org owner comes from the
        Owner role's implicit project access (org level ≥ Admin), not from
        organization.owner_id. No-op in community builds.
        """
        try:
            from rhesis.backend.app.scope import bypass_tenant_filter
            from rhesis.backend.ee.rbac.models import OrganizationMember, Role
        except ImportError:
            return
        with bypass_tenant_filter():
            owner_role = (
                db.query(Role)
                .filter_by(name="Owner", is_built_in=True, organization_id=None)
                .first()
            )
            existing = (
                db.query(OrganizationMember)
                .filter_by(organization_id=org_id, user_id=user_id)
                .first()
            )
        if owner_role is None:
            return
        if existing is None:
            db.add(
                OrganizationMember(organization_id=org_id, user_id=user_id, role_id=owner_role.id)
            )
        else:
            existing.role_id = owner_role.id
        db.flush()

    def _point_session(self, db, org_id: uuid.UUID) -> None:
        from sqlalchemy import text

        db.execute(text('SET "app.current_organization" = :o'), {"o": str(org_id)})

    def _create_project(self, db, org_id: uuid.UUID, user_id: uuid.UUID) -> uuid.UUID:
        from sqlalchemy import text

        project_id = uuid.uuid4()
        db.execute(
            text(
                "INSERT INTO project (id, name, organization_id, user_id, is_active) "
                "VALUES (:id, :name, :oid, :uid, true)"
            ),
            {
                "id": str(project_id),
                "name": f"WSProj-{project_id.hex[:8]}",
                "oid": str(org_id),
                "uid": str(user_id),
            },
        )
        db.flush()
        return project_id

    @pytest.mark.asyncio
    async def test_org_owner_allowed_for_project_channel(self, test_db):
        """Org owner is authorized to subscribe to a project channel (community tier)."""
        db = test_db
        org_id = self._create_org(db)
        user_id = self._create_user(db, org_id)
        self._set_owner(db, org_id, user_id)
        self._assign_owner_role(db, org_id, user_id)
        self._point_session(db, org_id)
        project_id = self._create_project(db, org_id, user_id)

        user = _fake_user(user_id=user_id, org_id=org_id)

        authorizer = ChannelAuthorizer()
        ok, err = await authorizer.authorize(
            user, f"project:{project_id}", db=db, principal=resolve_principal(user)
        )

        assert ok is True, f"Org owner should be allowed; err={err}"

    @pytest.mark.asyncio
    async def test_nonexistent_project_channel_denied(self, test_db):
        """A project channel for a project that doesn't exist in the org is denied."""
        db = test_db
        org_id = self._create_org(db)
        user_id = self._create_user(db, org_id)
        self._set_owner(db, org_id, user_id)
        self._point_session(db, org_id)

        user = _fake_user(user_id=user_id, org_id=org_id)
        ghost_project = uuid.uuid4()  # never created

        authorizer = ChannelAuthorizer()
        ok, err = await authorizer.authorize(
            user, f"project:{ghost_project}", db=db, principal=resolve_principal(user)
        )

        assert ok is False, "Subscription to a nonexistent project channel must be denied"

    @pytest.mark.asyncio
    async def test_cross_org_project_channel_denied(self, test_db):
        """A user cannot subscribe to another org's project channel (fail-closed)."""
        db = test_db
        # Org A owns the project.
        org_a = self._create_org(db)
        owner_a = self._create_user(db, org_a)
        self._set_owner(db, org_a, owner_a)
        self._point_session(db, org_a)
        project_a = self._create_project(db, org_a, owner_a)

        # Org B user tries to subscribe to org A's project channel.
        org_b = self._create_org(db)
        user_b = self._create_user(db, org_b)
        self._set_owner(db, org_b, user_b)
        # The WS session GUC is the subscriber's own org (as the manager sets it).
        self._point_session(db, org_b)

        user = _fake_user(user_id=user_b, org_id=org_b)

        authorizer = ChannelAuthorizer()
        ok, err = await authorizer.authorize(
            user, f"project:{project_a}", db=db, principal=resolve_principal(user)
        )

        assert ok is False, "Cross-org project channel subscription must be denied"
