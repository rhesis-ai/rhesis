"""Community tier: only the org owner invites or removes members, and the owner stays.

Runs over real HTTP so the route-derived ``member:create`` / ``member:delete`` checks fire.
"""

import uuid

import pytest

from rhesis.backend.app.auth.rbac import (
    DefaultAuthorizationProvider,
    get_authorization_provider,
    set_authorization_provider,
)
from rhesis.backend.app.crud import user as user_crud
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


@pytest.fixture
def org(test_db):
    suffix = uuid.uuid4().hex[:8]
    organization, owner, owner_token = create_test_organization_and_user(
        test_db, f"Members {suffix}", f"owner-{suffix}@rhesis-test.com", "Owner"
    )
    member = create_test_user(test_db, organization.id, f"member-{suffix}@rhesis-test.com")
    _demote_to_member(test_db, organization.id, member.id)
    member_token = create_test_api_token(test_db, member)
    test_db.commit()
    return {
        "id": organization.id,
        "owner": owner,
        "member": member,
        "owner_auth": {"Authorization": f"Bearer {owner_token.token}"},
        "member_auth": {"Authorization": f"Bearer {member_token.token}"},
    }


def _invite(client, headers):
    email = f"invitee-{uuid.uuid4().hex[:8]}@rhesis-test.com"
    return client.post("/users/", json={"email": email, "send_invite": False}, headers=headers)


def test_member_cannot_invite(client, org):
    assert _invite(client, org["member_auth"]).status_code == 403


def test_member_cannot_remove_the_owner(client, test_db, org):
    response = client.delete(f"/users/{org['owner'].id}", headers=org["member_auth"])

    assert response.status_code == 403
    test_db.refresh(org["owner"])
    assert org["owner"].organization_id == org["id"]


def test_owner_can_invite(client, org, monkeypatch):
    monkeypatch.setattr(
        "rhesis.backend.app.routers.user.validate_and_normalize_email",
        lambda email, check_deliverability=False: email,
    )
    response = _invite(client, org["owner_auth"])

    assert response.status_code == 200, response.text


def test_owner_cannot_be_removed_by_anyone(test_db, org):
    with pytest.raises(ValueError, match="owner"):
        user_crud.delete_user(
            test_db,
            target_user_id=org["owner"].id,
            organization_id=str(org["id"]),
            user_id=str(org["member"].id),
        )
