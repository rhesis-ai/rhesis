"""SDK connector ``register``: project access is not enough, it needs ``connector:create``."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import patch

import pytest

from rhesis.backend.app.auth.capabilities import get_all_capabilities
from rhesis.backend.app.auth.principal import Principal
from rhesis.backend.app.services.connector.manager import ConnectionManager
from rhesis.backend.app.services.connector.schemas import WebSocketConnectionContext
from rhesis.backend.ee.rbac.models import permissions_for_built_in_role
from tests.backend.ee.rbac._rbac_helpers import (
    _add_project_member,
    _assign_org_role,
    _assign_project_role,
    _create_org,
    _create_project,
    _create_user,
    _ee_provider_active,
)
from tests.backend.fixtures.rls import scope_to_org


@pytest.fixture(autouse=True)
def _no_redis():
    with patch("rhesis.backend.app.services.connector.manager.redis_manager") as redis:
        redis.is_available = False
        yield


@pytest.fixture
def org(test_db):
    org_id = _create_org(test_db)
    return org_id, _create_project(test_db, org_id), _create_user(test_db, org_id)


def _register(db, org_id, project_id, user_id, principal) -> bool:
    manager = ConnectionManager()
    context = WebSocketConnectionContext(
        user_id=str(user_id),
        organization_id=str(org_id),
        principal=principal,
    )
    manager._contexts[context.connection_id] = context
    scope_to_org(db, org_id)
    with _ee_provider_active():
        return asyncio.run(
            manager._authorize_and_register(
                context.connection_id, str(project_id), "development", db=db
            )
        )


def _session(user_id, org_id) -> Principal:
    return Principal(user_id=user_id, organization_id=org_id, kind="session")


@pytest.mark.parametrize(
    ("org_role", "project_role", "registers"),
    [
        ("Member", None, True),
        ("Viewer", None, False),
        # A project role above the org role counts, since the check is per project.
        ("Viewer", "Member", True),
    ],
)
def test_register_needs_connector_create(test_db, org, org_role, project_role, registers):
    org_id, project_id, user_id = org
    _assign_org_role(test_db, org_id, user_id, org_role)
    if project_role:
        _assign_project_role(test_db, org_id, project_id, user_id, project_role)
    else:
        _add_project_member(test_db, org_id, project_id, user_id)

    assert _register(test_db, org_id, project_id, user_id, _session(user_id, org_id)) is registers


def test_viewer_scoped_token_cannot_register(test_db, org):
    org_id, project_id, user_id = org
    _assign_org_role(test_db, org_id, user_id, "Member")
    _add_project_member(test_db, org_id, project_id, user_id)
    viewer_scopes = frozenset(permissions_for_built_in_role("Viewer", get_all_capabilities()))
    token = Principal(user_id=user_id, organization_id=org_id, kind="token", scopes=viewer_scopes)

    assert _register(test_db, org_id, project_id, user_id, token) is False


def test_connection_without_principal_is_refused(test_db, org):
    org_id, project_id, user_id = org
    _assign_org_role(test_db, org_id, user_id, "Owner")

    assert _register(test_db, org_id, project_id, user_id, None) is False


def test_unknown_project_is_refused(test_db, org):
    org_id, _, user_id = org
    _assign_org_role(test_db, org_id, user_id, "Owner")

    assert _register(test_db, org_id, uuid.uuid4(), user_id, _session(user_id, org_id)) is False


@pytest.mark.parametrize("path", ["/connector/trigger", "/connector/trace"])
def test_http_writes_need_connector_create(path):
    from rhesis.backend.app.auth.rbac import enforced_capability_for_route
    from rhesis.backend.app.main import app

    (route,) = [r for r in app.routes if getattr(r, "path", None) == path]
    assert enforced_capability_for_route(route) == "connector:create"
