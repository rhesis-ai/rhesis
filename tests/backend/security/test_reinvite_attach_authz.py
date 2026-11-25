"""Community tier: attaching an existing account to the org is owner-only.

``POST /users/`` re-invites an existing org-less account by setting its
``organization_id`` -- an immediate, acceptance-free attach, since that account
already has working credentials. The owner-only ``member:create`` gate must hold
for this path regardless of the request's active project.

The gate is evaluated org-scoped (``project_id=None``). A plain member who is
enrolled in a project and sends that project as the active one (``X-Project-Id``)
must not be able to use the project membership to pass an org-level member check.

The ``client`` fixture overrides ``get_tenant_db_session``, so the header never
reaches the session scope there; binding ``db.info['_scope']`` the way
``get_tenant_db_session`` does for a real ``X-Project-Id`` header reproduces it.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/security/test_reinvite_attach_authz.py -v
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime

import pytest

from rhesis.backend.app import models
from rhesis.backend.app.auth.rbac import (
    DefaultAuthorizationProvider,
    get_authorization_provider,
    set_authorization_provider,
)
from rhesis.backend.app.models.project_membership import ProjectMembership
from rhesis.backend.app.scope import RequestScope, bypass_tenant_filter
from tests.backend.fixtures.rls import scope_to_org
from tests.backend.fixtures.test_setup import (
    create_test_api_token,
    create_test_organization_and_user,
    create_test_user,
)
from tests.backend.security.test_authz_http_enforcement import _demote_to_member

pytestmark = [pytest.mark.security, pytest.mark.integration]


@pytest.fixture(autouse=True)
def _community_provider():
    previous = get_authorization_provider()
    set_authorization_provider(DefaultAuthorizationProvider())
    try:
        yield
    finally:
        set_authorization_provider(previous)


@pytest.fixture(autouse=True)
def _no_dns(monkeypatch):
    # The re-invite path validates the email's deliverability; skip the DNS check.
    monkeypatch.setattr(
        "rhesis.backend.app.routers.user.validate_and_normalize_email",
        lambda email, check_deliverability=False: email,
    )


def _create_project(db, org_id, owner_id) -> uuid.UUID:
    scope_to_org(db, org_id)
    project = models.Project(
        name=f"Reinvite-{uuid.uuid4().hex[:8]}",
        organization_id=org_id,
        owner_id=owner_id,
        user_id=owner_id,
    )
    db.add(project)
    db.flush()
    return project.id


def _enroll(db, org_id, project_id, user_id) -> None:
    scope_to_org(db, org_id)
    db.add(
        ProjectMembership(
            project_id=project_id,
            user_id=user_id,
            organization_id=org_id,
            role_id=None,
        )
    )
    db.flush()


def _org_of(db, user_id):
    db.expire_all()
    with bypass_tenant_filter():
        user = db.query(models.User).filter_by(id=user_id).first()
        return user.organization_id if user is not None else None


@pytest.fixture
def ctx(test_db):
    suffix = f"{datetime.now():%Y%m%d%H%M%S}_{uuid.uuid4().hex[:8]}"
    org, owner, owner_token = create_test_organization_and_user(
        test_db, f"Reinvite {suffix}", f"owner-{suffix}@rhesis-test.com", "Owner"
    )
    owner.is_email_verified = True

    # A plain org member (not the owner), enrolled in a project of the org.
    member = create_test_user(test_db, org.id, f"member-{suffix}@rhesis-test.com")
    _demote_to_member(test_db, org.id, member.id)
    member.is_email_verified = True
    project = _create_project(test_db, org.id, owner.id)
    _enroll(test_db, org.id, project, member.id)

    # An existing account that left / was removed from an org (org-less).
    returning = create_test_user(test_db, None, f"returning-{suffix}@rhesis-test.com")

    member_token = create_test_api_token(test_db, member)
    owner_token_obj = create_test_api_token(test_db, owner)
    test_db.commit()
    return {
        "db": test_db,
        "org_id": org.id,
        "project_id": project,
        "owner": owner,
        "member": member,
        "returning": returning,
        "member_auth": {"Authorization": f"Bearer {member_token.token}"},
        "owner_auth": {"Authorization": f"Bearer {owner_token_obj.token}"},
    }


@contextmanager
def _active(db, org_id, user, project_id):
    previous = db.info.get("_scope")
    db.info["_scope"] = RequestScope(
        organization_id=str(org_id),
        user_id=str(user.id),
        project_id=str(project_id) if project_id else None,
    )
    try:
        yield
    finally:
        db.info["_scope"] = previous


def _reinvite(client, ctx, headers, active_project):
    body = {"email": ctx["returning"].email, "send_invite": False}
    with _active(ctx["db"], ctx["org_id"], ctx["member"], active_project):
        extra = {"X-Project-Id": str(active_project)} if active_project else {}
        return client.post("/users/", json=body, headers={**headers, **extra})


def test_member_cannot_reinvite_even_with_active_project(client, ctx):
    """A project membership must not let a plain member attach an existing account."""
    resp = _reinvite(client, ctx, ctx["member_auth"], ctx["project_id"])

    assert resp.status_code == 403, resp.text
    assert _org_of(ctx["db"], ctx["returning"].id) is None


def test_member_cannot_reinvite_without_active_project(client, ctx):
    resp = _reinvite(client, ctx, ctx["member_auth"], None)

    assert resp.status_code == 403, resp.text
    assert _org_of(ctx["db"], ctx["returning"].id) is None


def test_owner_can_reinvite(client, ctx):
    """The owner may still attach a returning account (no over-blocking)."""
    with _active(ctx["db"], ctx["org_id"], ctx["owner"], None):
        resp = client.post(
            "/users/",
            json={"email": ctx["returning"].email, "send_invite": False},
            headers=ctx["owner_auth"],
        )

    assert resp.status_code == 200, resp.text
    assert str(_org_of(ctx["db"], ctx["returning"].id)) == str(ctx["org_id"])
