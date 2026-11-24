"""Members manage their own API tokens over HTTP; Viewers can't touch tokens.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/rbac/test_member_token_routes.py -v
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from fastapi import status

from tests.backend.ee.rbac._rbac_helpers import _assign_org_role, _ee_provider_active, _rbac_enabled
from tests.backend.fixtures.rls import scope_to_org
from tests.backend.fixtures.test_setup import (
    create_test_api_token,
    create_test_organization_and_user,
    create_test_user,
)


def _auth(token) -> dict:
    return {"Authorization": f"Bearer {token.token}"}


def _make_user(test_db, role_name: str):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    org, user, token = create_test_organization_and_user(
        test_db,
        f"Token Routes {role_name} {ts}_{suffix}",
        f"tokens_{role_name.lower()}_{suffix}@rhesis-test.com",
        f"Tokens {role_name}",
    )
    org.owner_id = None
    test_db.flush()
    _assign_org_role(test_db, org.id, user.id, role_name)
    test_db.commit()
    return org, user, token


def _add_user(test_db, org, role_name: str):
    scope_to_org(test_db, org.id)
    suffix = uuid.uuid4().hex[:8]
    user = create_test_user(test_db, org.id, f"tokens_peer_{suffix}@rhesis-test.com", "Peer")
    token = create_test_api_token(test_db, user)
    _assign_org_role(test_db, org.id, user.id, role_name)
    test_db.commit()
    return user, token


@pytest.mark.ee
@pytest.mark.integration
class TestMemberTokenRoutes:
    def test_member_manages_own_tokens(self, client, test_db):
        _org, _user, auth_token = _make_user(test_db, "Member")
        headers = _auth(auth_token)
        with _ee_provider_active(), _rbac_enabled():
            created = client.post("/tokens/", json={"name": "sdk"}, headers=headers)
            assert created.status_code == status.HTTP_200_OK, created.text
            token_id = created.json()["id"]

            listed = client.get("/tokens/", headers=headers)
            assert listed.status_code == status.HTTP_200_OK, listed.text
            assert token_id in {t["id"] for t in listed.json()}

            refreshed = client.post(
                f"/tokens/{token_id}/refresh", json={"expires_in_days": 30}, headers=headers
            )
            assert refreshed.status_code == status.HTTP_200_OK, refreshed.text
            assert refreshed.json()["access_token"] != created.json()["access_token"]

            deleted = client.delete(f"/tokens/{token_id}", headers=headers)
            assert deleted.status_code == status.HTTP_200_OK, deleted.text

    def test_member_bulk_deletes_own_tokens(self, client, test_db):
        _org, _user, auth_token = _make_user(test_db, "Member")
        headers = _auth(auth_token)
        with _ee_provider_active(), _rbac_enabled():
            ids = [
                client.post("/tokens/", json={"name": f"t{i}"}, headers=headers).json()["id"]
                for i in range(2)
            ]
            resp = client.request(
                "DELETE", "/tokens/bulk", json={"token_ids": ids}, headers=headers
            )
        assert resp.status_code == status.HTTP_200_OK, resp.text

    def test_member_gets_404_on_another_users_token(self, client, test_db):
        org, _owner, owner_auth = _make_user(test_db, "Member")
        _peer, peer_auth = _add_user(test_db, org, "Member")
        with _ee_provider_active(), _rbac_enabled():
            token_id = client.post(
                "/tokens/", json={"name": "mine"}, headers=_auth(owner_auth)
            ).json()["id"]

            peer = _auth(peer_auth)
            assert client.get(f"/tokens/{token_id}", headers=peer).status_code == 404
            assert (
                client.post(
                    f"/tokens/{token_id}/refresh", json={"expires_in_days": 1}, headers=peer
                ).status_code
                == 404
            )
            assert client.delete(f"/tokens/{token_id}", headers=peer).status_code == 404
            assert token_id not in {t["id"] for t in client.get("/tokens/", headers=peer).json()}

            # The owner's token survived the peer's attempts.
            mine = client.get(f"/tokens/{token_id}", headers=_auth(owner_auth))
        assert mine.status_code == status.HTTP_200_OK

    @pytest.mark.parametrize(
        ("method", "path", "body", "permission"),
        [
            ("GET", "/tokens/", None, "token:read"),
            ("POST", "/tokens/", {"name": "nope"}, "token:create"),
            # Refresh hands back a new token value, so it is gated like minting.
            ("POST", f"/tokens/{uuid.uuid4()}/refresh", {"expires_in_days": 1}, "token:create"),
            ("DELETE", f"/tokens/{uuid.uuid4()}", None, "token:delete"),
        ],
    )
    def test_viewer_is_refused(self, client, test_db, method, path, body, permission):
        _org, _user, auth_token = _make_user(test_db, "Viewer")
        with _ee_provider_active(), _rbac_enabled():
            resp = client.request(method, path, json=body, headers=_auth(auth_token))
        assert resp.status_code == status.HTTP_403_FORBIDDEN, resp.text
        assert resp.headers.get("X-Accepted-Permissions") == permission

    def test_member_cannot_request_scopes_beyond_role(self, client, test_db):
        _org, _user, auth_token = _make_user(test_db, "Member")
        with _ee_provider_active(), _rbac_enabled():
            resp = client.post(
                "/tokens/",
                json={"name": "wide", "scopes": ["role:manage"]},
                headers=_auth(auth_token),
            )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT, resp.text
        assert "role:manage" in resp.json()["detail"]

    def test_member_can_request_scopes_within_role(self, client, test_db):
        _org, _user, auth_token = _make_user(test_db, "Member")
        with _ee_provider_active(), _rbac_enabled():
            resp = client.post(
                "/tokens/",
                json={"name": "narrow", "scopes": ["test_set:read", "token:read"]},
                headers=_auth(auth_token),
            )
        assert resp.status_code == status.HTTP_200_OK, resp.text
