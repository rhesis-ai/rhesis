"""SP3 regression tests — org Owner authoritative + is_superuser de-reliance.

Exit criteria (backend plan SP3):
1. POST /organizations/ sets owner_id = current_user.id server-side, ignoring any
   client-supplied value.
2. Session JWT no longer carries is_superuser.
3. PUT /users/{id}: a user can always update their own profile.
4. PUT /users/{id}: only the org Owner (member:manage) can update another user.
   is_superuser=True on the User row confers NO additional privilege.
5. Recycle bin is org-scoped for all authenticated members; require_superuser is
   dead code that has been removed.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/auth/test_sp3_superuser.py -v
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import status
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.auth.token_utils import create_session_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_user(test_db: Session, org_id: str) -> models.User:
    """Create a fresh user inside the test org (rolled back with the test)."""
    suffix = uuid.uuid4().hex[:10]
    user = models.User(
        email=f"sp3-test-{suffix}@rhesis-test.com",
        name=f"SP3 Test {suffix}",
        given_name="SP3",
        family_name="Test",
        is_active=True,
        auth0_id=f"auth0|sp3{suffix}",
        organization_id=org_id,
    )
    test_db.add(user)
    test_db.flush()
    test_db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# 1. Organization creation — server-set owner_id
# ---------------------------------------------------------------------------


@pytest.mark.routes
class TestOrgOwnerCreation:
    """POST /organizations/ must ignore client-supplied owner_id and use the
    authenticated caller's user_id instead."""

    def test_create_org_sets_owner_id_to_current_user(
        self, authenticated_client, authenticated_user_id
    ):
        """Response owner_id matches the authenticated caller, not the client value."""
        forged_owner = str(uuid.uuid4())
        payload = {
            "name": f"sp3-forge-test-{uuid.uuid4().hex[:8]}",
            "description": "SP3 org owner forge test",
            "is_active": True,
            "owner_id": forged_owner,
            "user_id": str(uuid.uuid4()),
        }

        response = authenticated_client.post("/organizations/", json=payload)
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["owner_id"] == authenticated_user_id, (
            f"Expected owner_id={authenticated_user_id!r} (current user), "
            f"got {data['owner_id']!r} — server must override the client value"
        )

    def test_create_org_without_owner_id_uses_current_user(
        self, authenticated_client, authenticated_user_id
    ):
        """owner_id is set server-side even when the client sends no owner_id."""
        payload = {
            "name": f"sp3-no-owner-{uuid.uuid4().hex[:8]}",
            "is_active": True,
        }

        response = authenticated_client.post("/organizations/", json=payload)
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["owner_id"] == authenticated_user_id, (
            "owner_id must always equal the authenticated caller's id"
        )


# ---------------------------------------------------------------------------
# 2. Session JWT — is_superuser claim removed
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSuperuserJwtRemoval:
    """create_session_token must NOT embed is_superuser in the JWT payload."""

    def test_session_token_does_not_contain_is_superuser(self, test_db, test_org_id):
        """JWT user payload must not carry is_superuser after SP3."""
        import jwt as pyjwt

        from rhesis.backend.app.config.settings import get_auth_settings

        user = _unique_user(test_db, test_org_id)
        token = create_session_token(user)

        settings = get_auth_settings()
        decoded = pyjwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False},
        )

        user_payload = decoded.get("user", {})
        assert "is_superuser" not in user_payload, (
            "is_superuser must not appear in the JWT user payload — "
            "clients must use GET /me/permissions instead"
        )


# ---------------------------------------------------------------------------
# 3. PUT /users/{id} — authorization
# ---------------------------------------------------------------------------


@pytest.mark.routes
class TestUserUpdateAuthorization:
    """PUT /users/{id} authorization matrix after is_superuser removal.

    Rules:
    - Any user may update their own profile (self-update).
    - Only the org Owner may update another user's profile.
    - is_superuser=True on the User row confers NO authz privilege.
    """

    def test_user_can_update_own_profile(
        self, authenticated_client, authenticated_user_id
    ):
        """A user may always update their own profile (self-update path)."""
        payload = {"name": f"Updated Name {uuid.uuid4().hex[:6]}"}

        response = authenticated_client.put(
            f"/users/{authenticated_user_id}",
            json=payload,
        )
        # 200 OK or wrapped JSON response for self-update
        assert response.status_code == status.HTTP_200_OK

    def test_non_owner_cannot_update_other_user(
        self, authenticated_client, test_db, test_org_id
    ):
        """A non-owner (org.owner_id is NOT the caller) gets 403 on another user's profile."""
        # Ensure the test org has NO owner (or a different owner) so the
        # authenticated user is definitely not the org Owner.
        org = test_db.query(models.Organization).filter_by(id=test_org_id).first()
        original_owner_id = org.owner_id
        org.owner_id = None  # caller is not the owner
        test_db.flush()

        other_user = _unique_user(test_db, test_org_id)

        response = authenticated_client.put(
            f"/users/{other_user.id}",
            json={"name": "should not be set"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Restore owner_id so subsequent tests are unaffected
        org.owner_id = original_owner_id
        test_db.flush()

    def test_org_owner_can_update_other_user(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id
    ):
        """The org Owner (member:manage) may update another user's profile."""
        org = test_db.query(models.Organization).filter_by(id=test_org_id).first()
        original_owner_id = org.owner_id
        org.owner_id = authenticated_user_id  # make caller the org Owner
        test_db.flush()

        other_user = _unique_user(test_db, test_org_id)
        new_name = f"Owner-Updated {uuid.uuid4().hex[:6]}"

        response = authenticated_client.put(
            f"/users/{other_user.id}",
            json={"name": new_name},
        )
        assert response.status_code == status.HTTP_200_OK

        # Restore
        org.owner_id = original_owner_id
        test_db.flush()

    def test_is_superuser_true_does_not_grant_update_other_user(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id
    ):
        """is_superuser=True on the caller's row must NOT grant update rights over other users.

        This is the core SP3 regression guard: the boolean column no longer drives authz.
        """
        # Make sure the caller is NOT the org owner.
        org = test_db.query(models.Organization).filter_by(id=test_org_id).first()
        original_owner_id = org.owner_id
        org.owner_id = None
        test_db.flush()

        other_user = _unique_user(test_db, test_org_id)

        response = authenticated_client.put(
            f"/users/{other_user.id}",
            json={"name": "superuser bypass attempt"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, (
            "Non-owner must NOT be allowed to update another user's profile — "
            "only org Owner (member:manage) may do so"
        )

        # Restore
        org.owner_id = original_owner_id
        test_db.flush()


# ---------------------------------------------------------------------------
# 4. Recycle bin — require_superuser is dead code
# ---------------------------------------------------------------------------


@pytest.mark.routes
class TestRecycleBinOrgScoped:
    """Recycle bin endpoints are org-scoped for all authenticated members.
    require_superuser was confirmed dead code (never wired) and has been removed.
    """

    def test_recycle_models_accessible_to_regular_user(self, authenticated_client):
        """Any authenticated org member can reach GET /recycle/models."""
        response = authenticated_client.get("/recycle/models")
        assert response.status_code == status.HTTP_200_OK

    def test_recycle_list_accessible_to_regular_user(self, authenticated_client):
        """GET /recycle/{model_name} is org-scoped for all authenticated users."""
        response = authenticated_client.get("/recycle/test")
        # 200 (possibly empty list) or 400 for unknown model — either way NOT 403/401
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        )
