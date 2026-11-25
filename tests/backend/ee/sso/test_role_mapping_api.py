"""SSO role mapping admin API over HTTP (#3189): save checks, seen groups, preview,
and the Team tab's view of SSO-managed roles."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.scope import bypass_tenant_filter
from rhesis.backend.ee.rbac.models import OrganizationMember
from tests.backend.ee.rbac._rbac_helpers import (
    _assign_org_role,
    _builtin_role,
    _create_org,
    _create_project,
    _create_user,
    _ee_provider_active,
)
from tests.backend.ee.sso.test_sso_admin_authz_http import _auth, _context
from tests.backend.fixtures.rls import scope_to_org

pytestmark = [pytest.mark.ee, pytest.mark.integration]

BASE = {
    "enabled": True,
    "issuer_url": "https://idp.example.com/realms/acme",
    "client_id": "rhesis",
    "client_secret": "secret",
}


class Org:
    def __init__(self, db):
        self.db = db
        self.org, self.owner, self.token = _context(db, "Owner")
        scope_to_org(db, self.org.id)
        self.project = _create_project(db, self.org.id)
        self.role = {
            n: str(_builtin_role(db, n).id)
            for n in ("Owner", "Admin", "Auditor", "Member", "Viewer", "None")
        }
        db.commit()

    def member(self, role: str, groups: list[str] | None = None) -> uuid.UUID:
        scope_to_org(self.db, self.org.id)
        uid = _create_user(self.db, self.org.id)
        _assign_org_role(self.db, self.org.id, uid, role)
        if groups is not None:
            with bypass_tenant_filter():
                m = (
                    self.db.query(OrganizationMember)
                    .filter_by(organization_id=self.org.id, user_id=uid)
                    .first()
                )
                m.sso_claims = [{"path": ["groups"], "values": groups}]
                m.sso_claims_at = datetime.now(timezone.utc)
        self.db.commit()
        return uid

    def mapping(self, *rules, **kw) -> dict:
        return {"enabled": True, "rules": list(rules), **kw}

    def put(self, client, mapping=None, **extra):
        body = {**BASE, **extra}
        if mapping is not None:
            body["role_mapping"] = mapping
        with _ee_provider_active():
            return client.put(
                f"/organizations/{self.org.id}/sso", json=body, headers=_auth(self.token)
            )

    def post(self, client, path, body):
        with _ee_provider_active():
            return client.post(
                f"/organizations/{self.org.id}/sso/{path}", json=body, headers=_auth(self.token)
            )


@pytest.fixture
def org(test_db) -> Org:
    return Org(test_db)


class TestSave:
    def test_round_trip(self, client, org):
        mapping = org.mapping(
            {
                "group": "qa",
                "role_id": org.role["Member"],
                "projects": [{"project_id": str(org.project), "role_id": org.role["Admin"]}],
            },
            claim=["realm_access", "roles"],
            everyone_else="Viewer",
        )
        resp = org.put(client, mapping, provider="keycloak")
        assert resp.status_code == 200, resp.text
        with _ee_provider_active():
            got = client.get(f"/organizations/{org.org.id}/sso", headers=_auth(org.token)).json()
        assert got["provider"] == "keycloak"
        assert got["role_mapping"]["claim"] == ["realm_access", "roles"]
        assert got["role_mapping"]["rules"][0]["projects"][0]["project_id"] == str(org.project)

    def test_body_without_mapping_keeps_stored_mapping(self, client, org):
        org.put(client, org.mapping({"group": "a", "role_id": org.role["Admin"]}))
        assert org.put(client).status_code == 200
        with _ee_provider_active():
            got = client.get(f"/organizations/{org.org.id}/sso", headers=_auth(org.token)).json()
        assert got["role_mapping"]["rules"][0]["group"] == "a"

    def test_null_mapping_clears_it(self, client, org):
        org.put(client, org.mapping({"group": "a", "role_id": org.role["Admin"]}))
        with _ee_provider_active():
            resp = client.put(
                f"/organizations/{org.org.id}/sso",
                json={**BASE, "role_mapping": None},
                headers=_auth(org.token),
            )
        assert resp.json()["role_mapping"] is None

    def test_owner_rejected(self, client, org):
        resp = org.put(client, org.mapping({"group": "a", "role_id": org.role["Owner"]}))
        assert resp.status_code == 422
        assert "Owner" in resp.text

    @pytest.mark.parametrize("role", ["Owner", "Auditor", "None"])
    def test_bad_project_roles_rejected(self, client, org, role):
        rule = {
            "group": "a",
            "projects": [{"project_id": str(org.project), "role_id": org.role[role]}],
        }
        assert org.put(client, org.mapping(rule)).status_code == 422

    def test_other_orgs_project_rejected(self, client, org, test_db):
        other_org = _create_org(test_db)
        foreign = _create_project(test_db, other_org)
        test_db.commit()
        scope_to_org(test_db, org.org.id)
        rule = {
            "group": "a",
            "projects": [{"project_id": str(foreign), "role_id": org.role["Member"]}],
        }
        resp = org.put(client, org.mapping(rule))
        assert resp.status_code == 422
        assert "unknown project" in resp.text

    def test_unknown_role_rejected(self, client, org):
        resp = org.put(client, org.mapping({"group": "a", "role_id": str(uuid.uuid4())}))
        assert resp.status_code == 422

    def test_duplicate_groups_rejected(self, client, org):
        r = {"group": "a", "role_id": org.role["Admin"]}
        assert org.put(client, org.mapping(r, r)).status_code == 422

    def test_unknown_fields_rejected_quietly(self, client, org):
        # Extra keys are ignored, never stored.
        resp = org.put(client, org.mapping({"group": "a", "role_id": org.role["Admin"], "x": 1}))
        assert resp.status_code == 200
        assert "x" not in resp.json()["role_mapping"]["rules"][0]

    def test_stale_mapping_does_not_block_other_settings(self, client, org):
        org.put(client, org.mapping({"group": "a", "role_id": org.role["Admin"]}))
        stale = {"group": "a", "role_id": str(uuid.uuid4())}
        org.db.expire_all()
        with bypass_tenant_filter():
            o = org.db.query(Organization).filter_by(id=org.org.id).first()
            o.sso_config = {**o.sso_config, "role_mapping": org.mapping(stale)}
        org.db.commit()
        assert org.put(client, client_id="rotated").status_code == 200
        assert org.put(client, {**org.mapping(stale), "enabled": False}).status_code == 200

    def test_bad_provider_rejected(self, client, org):
        assert org.put(client, provider="github").status_code == 422


class TestSeenGroupsAndPreview:
    def test_seen_groups(self, client, org):
        org.member("Member", ["qa", "staff"])
        org.member("Member", ["staff"])
        org.member("Member")  # Never signed in with SSO.
        resp = org.post(client, "groups", {"claim": "groups"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["groups"] == [{"value": "staff", "members": 2}, {"value": "qa", "members": 1}]
        assert ["groups"] in body["claims"]

    def test_preview(self, client, org):
        org.member("Member", ["admins"])
        org.member("Admin", ["staff"])
        org.member("Viewer", ["staff"])  # Unchanged.
        org.member("Member")  # No SSO sign-in yet.
        mapping = org.mapping(
            {"group": "admins", "role_id": org.role["Admin"]},
            {"group": "staff", "role_id": org.role["Viewer"]},
        )
        resp = org.post(client, "role-mapping/preview", mapping)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        moves = sorted((c["from_role"], c["to_role"], c["less_access"]) for c in body["changes"])
        assert moves == [("Admin", "Viewer", True), ("Member", "Admin", False)]
        assert body["without_sign_in"] == 1

    def test_preview_shows_revoked_role(self, client, org):
        uid = org.member("Admin", ["left-admins"])
        with bypass_tenant_filter():
            m = org.db.query(OrganizationMember).filter_by(user_id=uid).first()
            m.sso_grants = {"org_role": org.role["Admin"], "projects": {}}
        org.db.commit()
        mapping = org.mapping({"group": "admins", "role_id": org.role["Admin"]})
        body = org.post(client, "role-mapping/preview", mapping).json()
        change = next(c for c in body["changes"] if c["user_id"] == str(uid))
        assert (change["from_role"], change["to_role"], change["less_access"]) == (
            "Admin",
            "None",
            True,
        )

    def test_preview_on_create_changes_nobody(self, client, org):
        org.member("Admin", ["staff"])
        mapping = org.mapping({"group": "staff", "role_id": org.role["Viewer"]}, apply="on_create")
        body = org.post(client, "role-mapping/preview", mapping).json()
        assert body["changes"] == [] and body["new_accounts_only"] is True

    def test_preview_never_lists_owner(self, client, org):
        mapping = org.mapping({"group": "x", "role_id": org.role["Viewer"]}, everyone_else="None")
        body = org.post(client, "role-mapping/preview", mapping).json()
        assert all(c["user_id"] != str(org.owner.id) for c in body["changes"])

    def test_preview_checks_refs(self, client, org):
        resp = org.post(
            client,
            "role-mapping/preview",
            org.mapping({"group": "x", "role_id": org.role["Owner"]}),
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize("path", ["groups", "role-mapping/preview"])
    def test_member_denied(self, client, test_db, path):
        other, _u, token = _context(test_db, "Member")
        with _ee_provider_active():
            resp = client.post(
                f"/organizations/{other.id}/sso/{path}",
                json={"claim": "groups"} if path == "groups" else {},
                headers=_auth(token),
            )
        assert resp.status_code == 403

    def test_other_org_denied(self, client, org, test_db):
        other, _u, _t = _context(test_db, "Owner")
        with _ee_provider_active():
            resp = client.post(
                f"/organizations/{other.id}/sso/groups",
                json={"claim": "groups"},
                headers=_auth(org.token),
            )
        assert resp.status_code == 403


class TestTeamTab:
    def test_managed_member_locked(self, client, org):
        managed = org.member("Member", ["admins"])
        free = org.member("Member", ["other"])
        org.put(client, org.mapping({"group": "admins", "role_id": org.role["Admin"]}))
        with _ee_provider_active():
            rows = client.get("/rbac/organization-members", headers=_auth(org.token)).json()
        by_user = {r["user_id"]: r for r in rows}
        assert by_user[str(managed)]["managed_by_sso_group"] == "admins"
        assert "member:manage" not in by_user[str(managed)]["permitted_actions"]
        assert by_user[str(free)]["managed_by_sso_group"] is None
        assert "member:manage" in by_user[str(free)]["permitted_actions"]

    def test_assign_refused_for_managed_member(self, client, org):
        managed = org.member("Member", ["admins"])
        org.put(client, org.mapping({"group": "admins", "role_id": org.role["Admin"]}))
        with _ee_provider_active():
            resp = client.put(
                f"/rbac/organization-members/{managed}/role",
                json={"role_id": org.role["Viewer"]},
                headers=_auth(org.token),
            )
        assert resp.status_code == 409

    def test_project_role_refused_for_managed_project(self, client, org):
        managed = org.member("Member", ["eng"])
        rule = {
            "group": "eng",
            "projects": [{"project_id": str(org.project), "role_id": org.role["Viewer"]}],
        }
        org.put(client, org.mapping(rule))
        url = f"/rbac/projects/{org.project}/members/{managed}/role"
        with _ee_provider_active():
            resp = client.put(url, json={"role_id": org.role["Admin"]}, headers=_auth(org.token))
        assert resp.status_code == 409

    def test_on_create_mode_does_not_lock(self, client, org):
        managed = org.member("Member", ["admins"])
        org.put(
            client,
            org.mapping({"group": "admins", "role_id": org.role["Admin"]}, apply="on_create"),
        )
        with _ee_provider_active():
            rows = client.get("/rbac/organization-members", headers=_auth(org.token)).json()
        row = next(r for r in rows if r["user_id"] == str(managed))
        assert row["managed_by_sso_group"] is None

    def test_disabled_sso_does_not_lock(self, client, org):
        managed = org.member("Member", ["admins"])
        org.put(
            client, org.mapping({"group": "admins", "role_id": org.role["Admin"]}), enabled=False
        )
        with _ee_provider_active():
            rows = client.get("/rbac/organization-members", headers=_auth(org.token)).json()
        row = next(r for r in rows if r["user_id"] == str(managed))
        assert row["managed_by_sso_group"] is None


class TestProviders:
    def test_catalog(self, client, org):
        with _ee_provider_active():
            resp = client.get(
                f"/organizations/{org.org.id}/sso/providers", headers=_auth(org.token)
            )
        assert resp.status_code == 200
        assert {p["key"] for p in resp.json()} >= {"keycloak", "entra", "oidc"}

    def test_detect(self, client, org):
        resp = org.post(client, "providers/detect", {"issuer_url": "https://x.okta.com"})
        assert resp.json() == {"provider": "okta"}

    def test_detect_member_denied(self, client, test_db):
        other, _u, token = _context(test_db, "Member")
        with _ee_provider_active():
            resp = client.post(
                f"/organizations/{other.id}/sso/providers/detect",
                json={"issuer_url": "https://x.okta.com"},
                headers=_auth(token),
            )
        assert resp.status_code == 403
