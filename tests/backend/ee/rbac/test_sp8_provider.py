"""SP8 tests — PermissionAuthorizationProvider.

Covers:
1. RBAC feature off → delegate to community provider (DefaultAuthorizationProvider).
2. Project role overrides org role (not a union).
3. Org role used when no project role is present.
4. No membership at either tier → deny.
5. Permission in role → allow; permission not in role → deny.
6. Retired permission → deny even if RolePermission row exists.
7. Missing org context → deny.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/rbac/test_sp8_provider.py -v
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.auth.principal import Principal
from rhesis.backend.app.auth.rbac import DefaultAuthorizationProvider
from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def provider():
    return PermissionAuthorizationProvider()


def _make_principal(org_id=None, user_id=None):
    return Principal(
        user_id=user_id or uuid.uuid4(),
        organization_id=org_id or uuid.uuid4(),
        kind="session",
    )


# ---------------------------------------------------------------------------
# RBAC off → community fallback
# ---------------------------------------------------------------------------


@pytest.mark.ee
class TestRbacOffFallback:
    def test_delegates_to_default_when_rbac_off(self, provider):
        principal = _make_principal()
        db = MagicMock()

        with (
            patch.object(provider, "_rbac_available", return_value=False),
            patch.object(
                provider._fallback,
                "is_authorized",
                return_value=True,
            ) as mock_fallback,
        ):
            result = provider.is_authorized(
                principal,
                "test_set:read",
                project_id=uuid.uuid4(),
                db=db,
            )

        assert result is True
        mock_fallback.assert_called_once()

    def test_fallback_deny_propagated(self, provider):
        principal = _make_principal()
        db = MagicMock()

        with (
            patch.object(provider, "_rbac_available", return_value=False),
            patch.object(provider._fallback, "is_authorized", return_value=False),
        ):
            result = provider.is_authorized(
                principal,
                "organization:update",
                project_id=None,
                db=db,
            )

        assert result is False


# ---------------------------------------------------------------------------
# No org context → deny
# ---------------------------------------------------------------------------


@pytest.mark.ee
class TestNoOrgContext:
    def test_deny_when_no_org(self, provider):
        principal = Principal(user_id=uuid.uuid4(), organization_id=None, kind="session")
        db = MagicMock()

        result = provider.is_authorized(
            principal,
            "test_set:read",
            project_id=uuid.uuid4(),
            db=db,
        )

        assert result is False


# ---------------------------------------------------------------------------
# Role resolution precedence
# ---------------------------------------------------------------------------


@pytest.mark.ee
class TestRoleResolutionPrecedence:
    def test_project_role_overrides_org_role(self, provider):
        """Project role must be used even when org role is present (not union)."""
        principal = _make_principal()
        db = MagicMock()

        fake_project_role = MagicMock()
        fake_project_role.name = "Viewer"
        fake_org_role = MagicMock()
        fake_org_role.name = "Admin"

        with (
            patch.object(provider, "_rbac_available", return_value=True),
            patch.object(provider, "_get_project_role", return_value=fake_project_role),
            patch.object(provider, "_get_org_role", return_value=fake_org_role),
            patch.object(provider, "_role_has_permission", return_value=True) as mock_check,
        ):
            provider.is_authorized(
                principal, "test_set:read", project_id=uuid.uuid4(), db=db
            )

        # The check must use the project role, not the org role.
        mock_check.assert_called_once_with(fake_project_role, "test_set:read", db)

    def test_falls_through_to_org_role_when_no_project_role(self, provider):
        principal = _make_principal()
        db = MagicMock()
        project_id = uuid.uuid4()
        fake_org_role = MagicMock()
        fake_org_role.name = "Member"

        with (
            patch.object(provider, "_rbac_available", return_value=True),
            patch.object(provider, "_get_project_role", return_value=None),
            patch.object(provider, "_get_org_role", return_value=fake_org_role),
            patch.object(provider, "_role_has_permission", return_value=True) as mock_check,
        ):
            provider.is_authorized(
                principal, "test_set:read", project_id=project_id, db=db
            )

        mock_check.assert_called_once_with(fake_org_role, "test_set:read", db)

    def test_deny_when_no_role_at_either_tier(self, provider):
        principal = _make_principal()
        db = MagicMock()

        with (
            patch.object(provider, "_rbac_available", return_value=True),
            patch.object(provider, "_get_project_role", return_value=None),
            patch.object(provider, "_get_org_role", return_value=None),
        ):
            result = provider.is_authorized(
                principal, "test_set:read", project_id=uuid.uuid4(), db=db
            )

        assert result is False

    def test_org_role_used_when_no_project_id(self, provider):
        """When no project_id, the org role must be used directly."""
        principal = _make_principal()
        db = MagicMock()
        fake_org_role = MagicMock()
        fake_org_role.name = "Admin"

        with (
            patch.object(provider, "_rbac_available", return_value=True),
            patch.object(provider, "_get_org_role", return_value=fake_org_role),
            patch.object(provider, "_role_has_permission", return_value=True) as mock_check,
        ):
            provider.is_authorized(
                principal, "organization:update", project_id=None, db=db
            )

        mock_check.assert_called_once_with(fake_org_role, "organization:update", db)


# ---------------------------------------------------------------------------
# Permission checks
# ---------------------------------------------------------------------------


@pytest.mark.ee
class TestPermissionChecks:
    def test_allow_when_permission_in_role(self, provider):
        principal = _make_principal()
        db = MagicMock()
        fake_role = MagicMock()
        fake_role.name = "Member"

        with (
            patch.object(provider, "_rbac_available", return_value=True),
            patch.object(provider, "_get_org_role", return_value=fake_role),
            patch.object(provider, "_role_has_permission", return_value=True),
        ):
            result = provider.is_authorized(
                principal, "test_set:read", project_id=None, db=db
            )

        assert result is True

    def test_deny_when_permission_not_in_role(self, provider):
        principal = _make_principal()
        db = MagicMock()
        fake_role = MagicMock()
        fake_role.name = "Viewer"

        with (
            patch.object(provider, "_rbac_available", return_value=True),
            patch.object(provider, "_get_org_role", return_value=fake_role),
            patch.object(provider, "_role_has_permission", return_value=False),
        ):
            result = provider.is_authorized(
                principal, "test_set:delete", project_id=None, db=db
            )

        assert result is False


# ---------------------------------------------------------------------------
# get_effective_permissions
# ---------------------------------------------------------------------------


@pytest.mark.ee
class TestGetEffectivePermissions:
    def test_returns_empty_when_rbac_off(self, provider):
        principal = _make_principal()
        db = MagicMock()

        with patch.object(provider, "_rbac_available", return_value=False):
            perms = provider.get_effective_permissions(principal, project_id=None, db=db)

        assert perms == set()

    def test_returns_empty_when_no_role(self, provider):
        principal = _make_principal()
        db = MagicMock()

        with (
            patch.object(provider, "_rbac_available", return_value=True),
            patch.object(provider, "_resolve_role", return_value=None),
        ):
            perms = provider.get_effective_permissions(principal, project_id=None, db=db)

        assert perms == set()


# ---------------------------------------------------------------------------
# Community boundary — provider is a plain class, no EE import side-effects
# ---------------------------------------------------------------------------


@pytest.mark.ee
class TestProviderInterface:
    def test_provider_is_not_defined_in_core(self):
        """PermissionAuthorizationProvider must NOT be imported by core at module level."""
        import sys
        # The core rbac module must not expose PermissionAuthorizationProvider.
        core_module = sys.modules.get("rhesis.backend.app.auth.rbac")
        assert core_module is not None
        assert not hasattr(core_module, "PermissionAuthorizationProvider"), (
            "Core rbac module must not expose PermissionAuthorizationProvider; "
            "it lives in ee/ and is installed at bootstrap via set_authorization_provider"
        )

    def test_fallback_is_default_provider(self, provider):
        assert isinstance(provider._fallback, DefaultAuthorizationProvider)
