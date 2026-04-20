"""Tests for SSO user provisioning (find_or_create_sso_user).

Uses mock DB and model objects to test the security-critical logic:
 - email normalisation
 - allowed_domains enforcement
 - org-scoped user lookup
 - cross-org collision prevention
 - auto-provisioning gate
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import SecretStr

from rhesis.backend.app.auth.constants import AuthProviderType
from rhesis.backend.app.auth.providers.base import AuthUser
from rhesis.backend.app.auth.sso_user_utils import SSOLoginError, find_or_create_sso_user
from rhesis.backend.app.schemas.sso_config import SSOConfig


def _sso_config(**overrides):
    defaults = dict(
        issuer_url="https://idp.example.com/realms/test",
        client_id="test-client",
        client_secret=SecretStr("test-secret"),
        auto_provision_users=False,
        allowed_domains=None,
    )
    defaults.update(overrides)
    return SSOConfig(**defaults)


def _auth_user(**overrides):
    defaults = dict(
        provider_type=AuthProviderType.OIDC,
        external_id="ext-123",
        email="alice@example.com",
        name="Alice Smith",
    )
    defaults.update(overrides)
    return AuthUser(**defaults)


def _organization(org_id=None):
    return SimpleNamespace(id=org_id or uuid4())


def _user_row(email, org_id, **extra):
    row = SimpleNamespace(
        id=uuid4(),
        email=email,
        organization_id=org_id,
        is_deleted=False,
        name="Existing",
        given_name=None,
        family_name=None,
        picture=None,
        provider_type=None,
        external_provider_id=None,
        last_login_at=None,
        is_email_verified=False,
    )
    for k, v in extra.items():
        setattr(row, k, v)
    return row


class _FakeQuery:
    """Minimal chainable mock for SQLAlchemy query results."""

    def __init__(self, results):
        self._results = list(results)

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._results.pop(0) if self._results else None


class TestFindOrCreateSSOUser:

    def _mock_db(self, query_results=None):
        """Return a mock db where query(...) returns sequential results."""
        db = MagicMock()
        results = list(query_results or [])

        def fake_query(*args, **kwargs):
            return _FakeQuery([results.pop(0)] if results else [])

        db.query.side_effect = fake_query
        return db

    # ── Invalid email ──

    def test_invalid_email_rejected(self):
        db = self._mock_db()
        org = _organization()
        config = _sso_config()
        auth_user = _auth_user(email="not-an-email")

        with pytest.raises(SSOLoginError) as exc_info:
            find_or_create_sso_user(db, auth_user, org, config)
        assert exc_info.value.reason_code == "invalid_email"

    # ── Domain enforcement ──

    def test_domain_not_allowed_rejected(self):
        db = self._mock_db()
        org = _organization()
        config = _sso_config(allowed_domains=["corp.com"])
        auth_user = _auth_user(email="alice@other.com")

        with pytest.raises(SSOLoginError) as exc_info:
            find_or_create_sso_user(db, auth_user, org, config)
        assert exc_info.value.reason_code == "domain_not_allowed"

    def test_domain_allowed_passes(self):
        org = _organization()
        existing_user = _user_row("alice@corp.com", org.id)
        db = self._mock_db(query_results=[existing_user])
        config = _sso_config(allowed_domains=["corp.com"])
        auth_user = _auth_user(email="alice@corp.com")

        user = find_or_create_sso_user(db, auth_user, org, config)
        assert user.email == "alice@corp.com"

    def test_no_domain_restriction_passes(self):
        org = _organization()
        existing_user = _user_row("alice@anything.com", org.id)
        db = self._mock_db(query_results=[existing_user])
        config = _sso_config(allowed_domains=None)
        auth_user = _auth_user(email="alice@anything.com")

        user = find_or_create_sso_user(db, auth_user, org, config)
        assert user is existing_user

    # ── Existing user in same org ──

    def test_existing_user_in_org_returned_and_updated(self):
        org = _organization()
        existing_user = _user_row("alice@example.com", org.id)
        db = self._mock_db(query_results=[existing_user])
        config = _sso_config()
        auth_user = _auth_user(name="Alice Updated")

        user = find_or_create_sso_user(db, auth_user, org, config)
        assert user is existing_user
        assert user.name == "Alice Updated"
        assert user.provider_type == AuthProviderType.OIDC
        assert user.is_email_verified is True

    # ── Cross-org collision ──

    def test_cross_org_collision_rejected(self):
        org = _organization()
        other_org = _organization()
        other_user = _user_row("alice@example.com", other_org.id)
        db = self._mock_db(query_results=[None, other_user])
        config = _sso_config()
        auth_user = _auth_user(email="alice@example.com")

        with pytest.raises(SSOLoginError) as exc_info:
            find_or_create_sso_user(db, auth_user, org, config)
        assert exc_info.value.reason_code == "cross_org_collision"

    # ── Auto-provisioning ──

    def test_auto_provision_disabled_rejected(self):
        db = self._mock_db(query_results=[None, None])
        org = _organization()
        config = _sso_config(auto_provision_users=False)
        auth_user = _auth_user()

        with pytest.raises(SSOLoginError) as exc_info:
            find_or_create_sso_user(db, auth_user, org, config)
        assert exc_info.value.reason_code == "auto_provision_disabled"

    @patch("rhesis.backend.app.crud.create_user")
    def test_auto_provision_creates_user(self, mock_create_user):
        db = self._mock_db(query_results=[None, None])
        org = _organization()
        config = _sso_config(auto_provision_users=True)
        auth_user = _auth_user(email="newuser@example.com", name="New User")

        fake_created = SimpleNamespace(id=uuid4(), email="newuser@example.com")
        mock_create_user.return_value = fake_created

        user = find_or_create_sso_user(db, auth_user, org, config)
        assert user is fake_created
        mock_create_user.assert_called_once()

        user_data = mock_create_user.call_args[0][1]
        assert user_data.email == "newuser@example.com"
        assert user_data.organization_id == org.id
        assert user_data.is_superuser is False
        assert user_data.is_email_verified is True


class TestSSOLoginErrorCarriesReasonCode:

    def test_reason_code_on_exception(self):
        err = SSOLoginError("test_code", "Custom message")
        assert err.reason_code == "test_code"
        assert str(err) == "Custom message"

    def test_default_message(self):
        err = SSOLoginError("some_code")
        assert str(err) == "SSO login failed"
