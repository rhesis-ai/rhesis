"""Exhaustive role x capability PDP matrix.

Proves, for every built-in role (Owner / Admin / Member / Viewer / None) and
every capability in the live catalog, that ``authorize()`` — the single
authorization decision point (``app/auth/rbac.py``) — agrees with the pure
oracle function ``permissions_for_built_in_role`` (``ee/rbac/models.py``).

``test_deny_matrix.py`` already proves the *zero-role* deny case, parametrized
over the ``Permission`` enum only. This file extends that idea to all five
built-in roles, positive and negative, over the full live catalog (route-
derived + enum-declared), at both scopes.

For project-scoped capabilities, every principal is explicitly enrolled in the
project (a ``project_membership`` row with ``role_id=None``, inheriting the
org role). This matters for Member/Viewer: ``PermissionAuthorizationProvider
._resolve_role`` only grants org-role fallback in a project context to
enrolled members — Admin/Owner get implicit access regardless, but enrolling
everyone uniformly keeps the setup identical across roles.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/security/test_role_capability_matrix.py -v --durations=10
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import get_all_capabilities
from rhesis.backend.app.auth.rbac import authorize
from rhesis.backend.ee.rbac.models import (
    BUILT_IN_ROLE_NAMES,
    SCOPE_ORGANIZATION,
    capability_scope,
    permissions_for_built_in_role,
)
from tests.backend.ee.rbac._rbac_helpers import (
    _add_project_member,
    _assign_org_role,
    _create_org,
    _create_project,
    _create_user,
    _ee_provider_active,
    _principal,
)


def _all_capabilities() -> list[str]:
    """Return the live capability catalog, self-registering if empty.

    Under the normal ``tests/backend`` suite, ``tests/backend/conftest.py``
    imports ``tests/backend/fixtures/client.py`` at module load, which
    imports ``rhesis.backend.app.main`` — whose own module-level code calls
    ``register_capabilities(app)`` — well before this file's
    ``pytest_generate_tests`` hook runs. A fully standalone invocation of
    just this file could theoretically reach collection without that chain
    having fired, so fall back to calling it directly: it is documented as
    idempotent, so doing this redundantly (the common case) is harmless.
    """
    capabilities = sorted(get_all_capabilities())
    if not capabilities:
        from rhesis.backend.app.auth.capabilities import register_capabilities
        from rhesis.backend.app.main import app

        register_capabilities(app)
        capabilities = sorted(get_all_capabilities())
    assert capabilities, (
        "Capability catalog is still empty after calling register_capabilities(app) "
        "— capability derivation itself must be broken, not just its ordering."
    )
    return capabilities


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize ``cap`` from the live catalog at collection time.

    A `pytest_generate_tests` hook (rather than a bare module-level global)
    keeps the import-order dependency on capability registration inside
    pytest's own collection machinery, so a violation surfaces as a normal
    collection error instead of failing at raw module import.
    """
    if "cap" in metafunc.fixturenames:
        metafunc.parametrize("cap", _all_capabilities())


@pytest.mark.ee
@pytest.mark.integration
@pytest.mark.security
@pytest.mark.parametrize("role_name", BUILT_IN_ROLE_NAMES)
def test_role_capability_matrix(cap: str, role_name: str, test_db: Session) -> None:
    """``authorize()`` must match the oracle for every (role, capability) pair."""
    db = test_db
    org_id = _create_org(db)
    user_id = _create_user(db, org_id)
    _assign_org_role(db, org_id, user_id, role_name)

    scope = capability_scope(cap)
    if scope == SCOPE_ORGANIZATION:
        project_id = None
    else:
        project_id = _create_project(db, org_id)
        _add_project_member(db, org_id, project_id, user_id, role_id=None)

    expected = cap in permissions_for_built_in_role(role_name, _all_capabilities())

    with _ee_provider_active():
        result = authorize(_principal(user_id, org_id), cap, project_id=project_id, db=db)

    assert result == expected, (
        f"authorize() disagreed with permissions_for_built_in_role() for "
        f"role='{role_name}' cap='{cap}' (scope={scope}): "
        f"expected {expected}, got {result}"
    )
