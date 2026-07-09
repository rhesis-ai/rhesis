"""SP8 tests — PermissionAuthorizationProvider.

Covers:
1. RBAC feature off → delegate to community provider (DefaultAuthorizationProvider).
2. Project role overrides org role (not a union).
3. Admin/Owner → implicit access to all projects (no project_membership row needed).
4. Member/Viewer → explicit enrollment required; no row → deny.
5. Member/Viewer with a membership row (role_id=NULL) → org role applied.
6. No membership at either tier → deny.
7. Permission in role → allow; permission not in role → deny.
8. Missing org context → deny.

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
# Helpers
# ---------------------------------------------------------------------------


def _make_role(name: str, level: int, is_built_in: bool = True) -> MagicMock:
    role = MagicMock()
    role.name = name
    role.level = level
    role.is_built_in = is_built_in
    return role


def _make_membership(role_id=None) -> MagicMock:
    m = MagicMock()
    m.role_id = role_id
    return m


# ---------------------------------------------------------------------------
# Role resolution precedence
# ---------------------------------------------------------------------------


@pytest.mark.ee
class TestRoleResolutionPrecedence:
    def test_lower_explicit_project_role_does_not_restrict_org_role(self, provider):
        """A lower explicit project role must not restrict a higher org role.

        Model A ("higher role wins, never restricts" — mirrors GitLab/GCP IAM):
        an org Admin/Owner keeps their org-level access to a project even if
        someone explicitly assigned them a lower project role there.
        """
        principal = _make_principal()
        db = MagicMock()
        project_id = uuid.uuid4()

        fake_project_role_id = uuid.uuid4()
        fake_membership = _make_membership(role_id=fake_project_role_id)
        fake_project_role = _make_role("Viewer", level=40)
        fake_org_role = _make_role("Admin", level=80)

        with (
            patch.object(provider, "_rbac_available", return_value=True),
            patch.object(provider, "_get_project_membership", return_value=fake_membership),
            patch.object(provider, "_load_role", return_value=fake_project_role),
            patch.object(provider, "_get_org_role", return_value=fake_org_role),
            patch.object(provider, "_role_has_permission", return_value=True) as mock_check,
        ):
            provider.is_authorized(principal, "test_set:read", project_id=project_id, db=db)

        # The higher-level org role must be used, not the lower project role.
        mock_check.assert_called_once_with(fake_org_role, "test_set:read", db)

    def test_higher_explicit_project_role_elevates_above_org_role(self, provider):
        """An explicit project role can still elevate access above the org role."""
        principal = _make_principal()
        db = MagicMock()
        project_id = uuid.uuid4()

        fake_project_role_id = uuid.uuid4()
        fake_membership = _make_membership(role_id=fake_project_role_id)
        fake_project_role = _make_role("Owner", level=100)
        fake_org_role = _make_role("Member", level=60)

        with (
            patch.object(provider, "_rbac_available", return_value=True),
            patch.object(provider, "_get_project_membership", return_value=fake_membership),
            patch.object(provider, "_load_role", return_value=fake_project_role),
            patch.object(provider, "_get_org_role", return_value=fake_org_role),
            patch.object(provider, "_role_has_permission", return_value=True) as mock_check,
        ):
            provider.is_authorized(principal, "test_set:delete", project_id=project_id, db=db)

        # The higher-level project role must be used, elevating above the org role.
        mock_check.assert_called_once_with(fake_project_role, "test_set:delete", db)

    def test_org_role_used_when_no_project_id(self, provider):
        """When no project_id, the org role must be used directly."""
        principal = _make_principal()
        db = MagicMock()
        fake_org_role = _make_role("Admin", level=80)

        with (
            patch.object(provider, "_rbac_available", return_value=True),
            patch.object(provider, "_get_org_role", return_value=fake_org_role),
            patch.object(provider, "_role_has_permission", return_value=True) as mock_check,
        ):
            provider.is_authorized(principal, "organization:update", project_id=None, db=db)

        mock_check.assert_called_once_with(fake_org_role, "organization:update", db)

    def test_deny_when_no_org_role_and_no_membership(self, provider):
        principal = _make_principal()
        db = MagicMock()

        with (
            patch.object(provider, "_rbac_available", return_value=True),
            patch.object(provider, "_get_project_membership", return_value=None),
            patch.object(provider, "_get_org_role", return_value=None),
        ):
            result = provider.is_authorized(
                principal, "test_set:read", project_id=uuid.uuid4(), db=db
            )

        assert result is False


# ---------------------------------------------------------------------------
# Admin / Owner implicit project access (no enrollment needed)
# ---------------------------------------------------------------------------


@pytest.mark.ee
class TestImplicitProjectAccess:
    """Admin and Owner get access to every project without a project_membership row."""

    @pytest.mark.parametrize("role_name,level", [("Owner", 100), ("Admin", 80)])
    def test_admin_owner_access_without_membership_row(self, provider, role_name, level):
        principal = _make_principal()
        db = MagicMock()
        project_id = uuid.uuid4()
        org_role = _make_role(role_name, level=level)

        with (
            patch.object(provider, "_rbac_available", return_value=True),
            patch.object(provider, "_get_project_membership", return_value=None),
            patch.object(provider, "_get_org_role", return_value=org_role),
            patch.object(provider, "_role_has_permission", return_value=True) as mock_check,
        ):
            result = provider.is_authorized(
                principal, "test_set:read", project_id=project_id, db=db
            )

        assert result is True
        mock_check.assert_called_once_with(org_role, "test_set:read", db)

    @pytest.mark.parametrize("role_name,level", [("Owner", 100), ("Admin", 80)])
    def test_admin_owner_access_with_membership_row_no_role(self, provider, role_name, level):
        """Membership row with NULL role_id still uses org role for Admin/Owner."""
        principal = _make_principal()
        db = MagicMock()
        project_id = uuid.uuid4()
        org_role = _make_role(role_name, level=level)
        membership = _make_membership(role_id=None)

        with (
            patch.object(provider, "_rbac_available", return_value=True),
            patch.object(provider, "_get_project_membership", return_value=membership),
            patch.object(provider, "_get_org_role", return_value=org_role),
            patch.object(provider, "_role_has_permission", return_value=True) as mock_check,
        ):
            result = provider.is_authorized(
                principal, "test_set:read", project_id=project_id, db=db
            )

        assert result is True
        mock_check.assert_called_once_with(org_role, "test_set:read", db)


# ---------------------------------------------------------------------------
# Member / Viewer explicit enrollment required
# ---------------------------------------------------------------------------


@pytest.mark.ee
class TestExplicitEnrollmentRequired:
    """Member and Viewer need an explicit project_membership row to access a project."""

    @pytest.mark.parametrize("role_name,level", [("Member", 60), ("Viewer", 40)])
    def test_member_viewer_denied_without_membership_row(self, provider, role_name, level):
        """No project_membership row → deny for Member and Viewer."""
        principal = _make_principal()
        db = MagicMock()
        project_id = uuid.uuid4()
        org_role = _make_role(role_name, level=level)

        with (
            patch.object(provider, "_rbac_available", return_value=True),
            patch.object(provider, "_get_project_membership", return_value=None),
            patch.object(provider, "_get_org_role", return_value=org_role),
        ):
            result = provider.is_authorized(
                principal, "test_set:read", project_id=project_id, db=db
            )

        assert result is False

    @pytest.mark.parametrize("role_name,level", [("Member", 60), ("Viewer", 40)])
    def test_member_viewer_allowed_with_membership_row_no_explicit_role(
        self, provider, role_name, level
    ):
        """Membership row with role_id=NULL → org role applies for Member/Viewer."""
        principal = _make_principal()
        db = MagicMock()
        project_id = uuid.uuid4()
        org_role = _make_role(role_name, level=level)
        membership = _make_membership(role_id=None)

        with (
            patch.object(provider, "_rbac_available", return_value=True),
            patch.object(provider, "_get_project_membership", return_value=membership),
            patch.object(provider, "_get_org_role", return_value=org_role),
            patch.object(provider, "_role_has_permission", return_value=True) as mock_check,
        ):
            result = provider.is_authorized(
                principal, "test_set:read", project_id=project_id, db=db
            )

        assert result is True
        mock_check.assert_called_once_with(org_role, "test_set:read", db)

    @pytest.mark.parametrize("role_name,level", [("Member", 60), ("Viewer", 40)])
    def test_explicit_project_role_overrides_for_member_viewer(self, provider, role_name, level):
        """Explicit project role overrides org role even for Member/Viewer."""
        principal = _make_principal()
        db = MagicMock()
        project_id = uuid.uuid4()
        project_role_id = uuid.uuid4()
        membership = _make_membership(role_id=project_role_id)
        # e.g. org Viewer given project-level Admin
        project_role = _make_role("Admin", level=80)
        org_role = _make_role(role_name, level=level)

        with (
            patch.object(provider, "_rbac_available", return_value=True),
            patch.object(provider, "_get_project_membership", return_value=membership),
            patch.object(provider, "_load_role", return_value=project_role),
            patch.object(provider, "_get_org_role", return_value=org_role),
            patch.object(provider, "_role_has_permission", return_value=True) as mock_check,
        ):
            result = provider.is_authorized(
                principal, "member:manage", project_id=project_id, db=db
            )

        assert result is True
        mock_check.assert_called_once_with(project_role, "member:manage", db)


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
            result = provider.is_authorized(principal, "test_set:read", project_id=None, db=db)

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
            result = provider.is_authorized(principal, "test_set:delete", project_id=None, db=db)

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


# ---------------------------------------------------------------------------
# Built-in role branch — permissions computed from code, not DB rows
# ---------------------------------------------------------------------------


@pytest.mark.ee
class TestBuiltInRoleBranch:
    """_role_has_permission must compute built-in permissions from code.

    These tests verify the branch introduced when the runtime sync was removed:
    built-in roles (is_built_in=True) must resolve permissions via
    permissions_for_built_in_role(), never via role_permission rows.
    """

    def _make_role(self, name: str, is_built_in: bool = True):
        role = MagicMock()
        role.name = name
        role.is_built_in = is_built_in
        return role

    def test_built_in_owner_has_known_capability(self, provider):
        """Owner (built-in) must hold any capability in the live catalog."""
        db = MagicMock()
        role = self._make_role("Owner", is_built_in=True)
        # Owner gets everything — pick a capability that is always present
        result = provider._role_has_permission(role, "test_set:read", db)
        assert result is True, "Owner built-in must hold test_set:read"

    def test_built_in_none_has_no_capability(self, provider):
        """None (built-in) must hold zero capabilities."""
        db = MagicMock()
        role = self._make_role("None", is_built_in=True)
        result = provider._role_has_permission(role, "test_set:read", db)
        assert result is False, "None built-in must hold no capabilities"

    def test_built_in_viewer_holds_read_not_delete(self, provider):
        """Viewer (built-in) holds :read caps but not :delete."""
        db = MagicMock()
        role = self._make_role("Viewer", is_built_in=True)
        assert provider._role_has_permission(role, "test_set:read", db) is True
        assert provider._role_has_permission(role, "test_set:delete", db) is False

    def test_built_in_does_not_query_db(self, provider):
        """Built-in role check must not call db.query at all."""
        db = MagicMock()
        role = self._make_role("Admin", is_built_in=True)
        provider._role_has_permission(role, "organization:update", db)
        db.query.assert_not_called()

    def test_custom_role_queries_db(self, provider):
        """Custom role (is_built_in=False) must fall through to the DB join."""
        db = MagicMock()
        role = self._make_role("QA Lead", is_built_in=False)
        # db.query chain: query → join → filter → first
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None  # deny
        result = provider._role_has_permission(role, "test_set:read", db)
        assert result is False
        db.query.assert_called_once()

    def test_get_effective_permissions_built_in_no_db(self, provider):
        """get_effective_permissions for a built-in role must not touch the DB."""
        from rhesis.backend.app.auth.capabilities import get_all_capabilities
        from rhesis.backend.ee.rbac.models import permissions_for_built_in_role

        principal = _make_principal()
        db = MagicMock()
        fake_role = self._make_role("Member", is_built_in=True)

        with (
            patch.object(provider, "_rbac_available", return_value=True),
            patch.object(provider, "_resolve_role", return_value=fake_role),
        ):
            perms = provider.get_effective_permissions(principal, project_id=None, db=db)

        expected = permissions_for_built_in_role("Member", get_all_capabilities())
        assert perms == expected
        db.query.assert_not_called()

    def test_get_effective_permissions_custom_role_queries_db(self, provider):
        """get_effective_permissions for a custom role must query role_permission."""
        principal = _make_principal()
        db = MagicMock()
        fake_role = self._make_role("Custom", is_built_in=False)

        mock_q = MagicMock()
        db.query.return_value = mock_q
        mock_q.join.return_value = mock_q
        mock_q.filter.return_value = mock_q
        mock_q.all.return_value = []

        with (
            patch.object(provider, "_rbac_available", return_value=True),
            patch.object(provider, "_resolve_role", return_value=fake_role),
        ):
            perms = provider.get_effective_permissions(principal, project_id=None, db=db)

        assert perms == set()
        db.query.assert_called_once()
