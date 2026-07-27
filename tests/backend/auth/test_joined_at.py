"""Tests for joined_at membership stamping."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.auth.constants import AuthProviderType
from rhesis.backend.app.auth.providers.base import AuthUser
from rhesis.backend.app.auth.user_utils import (
    find_or_create_user_from_auth,
    mark_user_joined_if_needed,
)
from rhesis.backend.app.schemas import UserCreate


@pytest.mark.unit
class TestMarkUserJoinedIfNeeded:
    def test_sets_joined_at_when_user_has_org(self, test_db: Session, test_org_id: str):
        user = crud.create_user(
            test_db,
            UserCreate(
                email=f"joined-{uuid.uuid4().hex[:8]}@example.com",
                organization_id=uuid.UUID(test_org_id),
            ),
        )
        test_db.flush()

        when = datetime(2026, 7, 13, 10, 0, tzinfo=timezone.utc)
        assert mark_user_joined_if_needed(user, when=when) is True
        assert user.joined_at == when

    def test_is_idempotent(self, test_db: Session, test_org_id: str):
        when = datetime(2026, 7, 13, 10, 0, tzinfo=timezone.utc)
        user = crud.create_user(
            test_db,
            UserCreate(
                email=f"joined-idem-{uuid.uuid4().hex[:8]}@example.com",
                organization_id=uuid.UUID(test_org_id),
                joined_at=when,
            ),
        )
        test_db.flush()

        assert mark_user_joined_if_needed(user) is False
        assert user.joined_at == when

    def test_no_op_without_organization(self, test_db: Session):
        user = crud.create_user(
            test_db,
            UserCreate(email=f"no-org-{uuid.uuid4().hex[:8]}@example.com"),
        )
        test_db.flush()

        assert mark_user_joined_if_needed(user) is False
        assert user.joined_at is None


@pytest.mark.unit
class TestFindOrCreateUserFromAuthJoinedAt:
    def test_stamps_joined_at_for_invited_org_member(self, test_db: Session, test_org_id: str):
        email = f"invite-accept-{uuid.uuid4().hex[:8]}@example.com"
        invited = crud.create_user(
            test_db,
            UserCreate(email=email, organization_id=uuid.UUID(test_org_id)),
        )
        test_db.commit()
        assert invited.joined_at is None

        auth_user = AuthUser(
            provider_type=AuthProviderType.GOOGLE,
            external_id="google-sub-123",
            email=email,
            name="Accepted Invite",
        )
        user = find_or_create_user_from_auth(test_db, auth_user)

        assert user.id == invited.id
        assert user.joined_at is not None
        assert user.last_login_at is not None

    def test_does_not_stamp_joined_at_for_orgless_signup(self, test_db: Session):
        email = f"signup-{uuid.uuid4().hex[:8]}@example.com"
        auth_user = AuthUser(
            provider_type=AuthProviderType.GOOGLE,
            external_id="google-sub-456",
            email=email,
            name="New Signup",
        )

        user = find_or_create_user_from_auth(test_db, auth_user)

        assert user.organization_id is None
        assert user.joined_at is None
        assert user.last_login_at is not None
