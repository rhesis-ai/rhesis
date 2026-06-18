"""SP12 — Auto-generated deny matrix from the capability registry.

Every capability in the ``Permission`` enum must deny a caller with no org
role in EE (PermissionAuthorizationProvider).  This test is parametrized
against :func:`~rhesis.backend.app.auth.capabilities.enumerate_permission_enum`
so new capabilities added to the enum are automatically covered — no extra
hand-written test needed.

Pass/fail signal:
- ``False`` from ``authorize()`` for an EE principal with no role → PASS (deny as expected).
- ``True`` → FAIL (unexpected allow — investigate whether the capability should
  really be accessible with no membership).

Note: Community provider *is not* tested here.  ``DefaultAuthorizationProvider``
intentionally allows any org member for non-owner-only capabilities; the deny
behaviour there is tested in ``test_rbac.py`` / ``test_providers.py``.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/security/test_deny_matrix.py -v
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import enumerate_permission_enum
from rhesis.backend.app.auth.principal import Principal
from rhesis.backend.app.auth.rbac import (
    authorize,
    get_authorization_provider,
    set_authorization_provider,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_org(db: Session) -> uuid.UUID:
    org_id = uuid.uuid4()
    db.execute(
        text("INSERT INTO organization (id, name, is_active) VALUES (:id, :name, true)"),
        {"id": str(org_id), "name": f"DMOrg-{org_id.hex[:8]}"},
    )
    db.flush()
    return org_id


def _create_user(db: Session, org_id: uuid.UUID) -> uuid.UUID:
    user_id = uuid.uuid4()
    db.execute(
        text(
            'INSERT INTO "user" (id, email, organization_id, is_active) '
            "VALUES (:id, :email, :oid, true)"
        ),
        {
            "id": str(user_id),
            "email": f"u-{user_id.hex[:8]}@dm.example",
            "oid": str(org_id),
        },
    )
    db.flush()
    return user_id


@contextmanager
def _ee_provider_no_role():
    """Install EE provider with RBAC on but NO membership row for the test principal.

    The principal has an org but no OrganizationMember row, so _get_org_role() returns
    None and the provider falls back to deny.
    """
    from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider

    previous = get_authorization_provider()
    set_authorization_provider(PermissionAuthorizationProvider())
    try:
        with (
            patch(
                "rhesis.backend.app.features.FeatureRegistry.is_available",
                return_value=True,
            ),
            patch.object(PermissionAuthorizationProvider, "_rbac_available", return_value=True),
        ):
            yield
    finally:
        set_authorization_provider(previous)


# ---------------------------------------------------------------------------
# Auto-generated deny matrix
# ---------------------------------------------------------------------------

# Capabilities granted to everyone in community by default (owner-bypass, etc.)
# and therefore meaningless to test in EE deny-matrix context are excluded here.
# All capabilities in the enum are tested — the expectation is that a principal
# with NO role is denied for every one of them.
_ALL_ENUM_CAPS = sorted(enumerate_permission_enum())


@pytest.mark.ee
@pytest.mark.integration
@pytest.mark.security
@pytest.mark.parametrize("cap", _ALL_ENUM_CAPS)
def test_no_role_principal_denied_for_capability(cap: str, test_db: Session) -> None:
    """EE: principal with no org role must be denied for every declared capability.

    This is the automated deny/IDOR backstop.  If a new capability is added to
    the ``Permission`` enum but is accidentally granted to the zero-role principal,
    this test fails and the developer must either fix the authorization logic or
    explicitly mark the capability as intentionally public.
    """
    db = test_db
    org_id = _create_org(db)
    user_id = _create_user(db, org_id)
    db.execute(text('SET "app.current_organization" = :o'), {"o": str(org_id)})

    # Principal with org context but NO membership row (no role assigned).
    principal = Principal(user_id=user_id, organization_id=org_id, kind="session")

    with _ee_provider_no_role():
        result = authorize(principal, cap, project_id=None, db=db)

    assert result is False, (
        f"Capability '{cap}' was unexpectedly ALLOWED for a principal with no org role. "
        "If this capability should be publicly accessible, document it and add an exemption "
        "here.  Otherwise, investigate the authorization provider logic."
    )


# ---------------------------------------------------------------------------
# SP12: X-Accepted-Permissions header surfaced by require_permission()
# ---------------------------------------------------------------------------


class TestAcceptedPermissionsHeader:
    """require_permission() must include X-Accepted-Permissions on 403."""

    def test_header_present_on_403(self, monkeypatch):
        """When authorize() denies, the dependency raises 403 with the header.

        Calls the dependency closure directly (no TestClient wiring) so the
        assertion is deterministic rather than conditional on a 403 occurring.
        """
        from types import SimpleNamespace

        from fastapi import HTTPException

        from rhesis.backend.app.auth.principal import Principal
        from rhesis.backend.app.auth.rbac import require_permission

        # Deny unconditionally; force org-scoped (no project) resolution.
        monkeypatch.setattr(
            "rhesis.backend.app.auth.rbac.resolve_principal",
            lambda u, **kw: Principal(
                user_id=uuid.uuid4(), organization_id=uuid.uuid4(), kind="session"
            ),
        )
        monkeypatch.setattr("rhesis.backend.app.auth.rbac.authorize", lambda *a, **kw: False)

        dependency = require_permission("test_set:read")

        fake_request = SimpleNamespace(state=SimpleNamespace())
        fake_db = SimpleNamespace(info={})
        fake_user = SimpleNamespace(id=uuid.uuid4(), organization_id=uuid.uuid4())

        with pytest.raises(HTTPException) as exc_info:
            dependency(request=fake_request, db=fake_db, current_user=fake_user)

        assert exc_info.value.status_code == 403
        assert exc_info.value.headers is not None
        assert exc_info.value.headers.get("X-Accepted-Permissions") == "test_set:read"
