"""SSO role mapping at sign-in, against a real database (#3189).

Drives ``resolve_sso_user`` (everything in the callback except minting tokens) with
the claims an IdP would send, then reads back org roles and project memberships.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.constants import AuthProviderType
from rhesis.backend.app.auth.providers.base import AuthUser
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.models.project_membership import ProjectMembership
from rhesis.backend.app.models.user import User
from rhesis.backend.app.scope import bypass_tenant_filter
from rhesis.backend.ee.rbac.models import OrganizationMember, Role
from rhesis.backend.ee.sso.router import resolve_sso_user
from rhesis.backend.ee.sso.schemas import MappingRule, ProjectGrant, RoleMapping, SSOConfig
from rhesis.backend.ee.sso.user_utils import SSOLoginError
from tests.backend.ee.rbac._rbac_helpers import (
    _add_project_member,
    _assign_org_role,
    _builtin_role,
    _create_org,
    _create_project,
    _create_user,
)

pytestmark = [pytest.mark.ee, pytest.mark.integration]


@contextmanager
def _rbac_on():
    with patch("rhesis.backend.app.features.FeatureRegistry.is_available", return_value=True):
        yield


class Env:
    """One org with two projects and a mapping helper."""

    def __init__(self, db: Session):
        self.db = db
        self.org_id = _create_org(db)
        self.support = _create_project(db, self.org_id)
        self.claims = _create_project(db, self.org_id)
        self.role = {
            n: _builtin_role(db, n).id
            for n in ("Owner", "Admin", "Auditor", "Member", "Viewer", "None")
        }

    @property
    def org(self) -> Organization:
        with bypass_tenant_filter():
            return self.db.query(Organization).filter_by(id=self.org_id).first()

    def config(self, *rules, **kw) -> SSOConfig:
        return SSOConfig(
            issuer_url="https://idp.example.com/realms/acme",
            client_id="rhesis",
            client_secret=SecretStr("s"),
            auto_provision_users=True,
            role_mapping=RoleMapping(enabled=True, rules=list(rules), **kw),
        )

    def rule(self, group, role=None, **projects) -> MappingRule:
        return MappingRule(
            group=group,
            role_id=self.role[role] if role else None,
            projects=[
                ProjectGrant(project_id=getattr(self, p), role_id=self.role[r])
                for p, r in projects.items()
            ],
        )

    def sign_in(self, email, config, groups=None, claims=None) -> User:
        raw = {"sub": email, "email": email}
        if groups is not None:
            raw["groups"] = groups
        raw.update(claims or {})
        auth_user = AuthUser(
            provider_type=AuthProviderType.OIDC, external_id=email, email=email, raw_data=raw
        )
        with _rbac_on():
            return resolve_sso_user(self.db, auth_user, self.org, config)

    def user(self, role: str | None = None) -> tuple[uuid.UUID, str]:
        uid = _create_user(self.db, self.org_id)
        if role:
            _assign_org_role(self.db, self.org_id, uid, role)
        with bypass_tenant_filter():
            email = self.db.query(User.email).filter_by(id=uid).scalar()
        return uid, email

    def org_role(self, user_id) -> str | None:
        self.db.flush()
        with bypass_tenant_filter():
            row = (
                self.db.query(Role.name)
                .join(OrganizationMember, OrganizationMember.role_id == Role.id)
                .filter(
                    OrganizationMember.organization_id == self.org_id,
                    OrganizationMember.user_id == user_id,
                )
                .first()
            )
        return row[0] if row else None

    def project_role(self, user_id, project_id) -> str | None:
        """Role name, "member" for a membership without a role, None for no membership."""
        with bypass_tenant_filter():
            m = (
                self.db.query(ProjectMembership)
                .filter_by(project_id=project_id, user_id=user_id)
                .first()
            )
            if m is None:
                return None
            if m.role_id is None:
                return "member"
            return self.db.query(Role.name).filter_by(id=m.role_id).scalar()

    def snapshot(self, user_id):
        self.db.flush()
        with bypass_tenant_filter():
            return (
                self.db.query(OrganizationMember.sso_claims)
                .filter_by(organization_id=self.org_id, user_id=user_id)
                .scalar()
            )


@pytest.fixture
def env(test_db: Session) -> Env:
    return Env(test_db)


class TestOrgRole:
    def test_existing_member_promoted(self, env):
        uid, email = env.user("Member")
        env.sign_in(email, env.config(env.rule("admins", "Admin")), ["admins"])
        assert env.org_role(uid) == "Admin"

    def test_highest_role_wins(self, env):
        uid, email = env.user("Member")
        cfg = env.config(env.rule("staff", "Viewer"), env.rule("audit", "Auditor"))
        env.sign_in(email, cfg, ["staff", "audit"])
        assert env.org_role(uid) == "Auditor"

    def test_downgrade_when_group_removed(self, env):
        uid, email = env.user("Member")
        cfg = env.config(env.rule("admins", "Admin"), env.rule("staff", "Viewer"))
        env.sign_in(email, cfg, ["admins", "staff"])
        env.sign_in(email, cfg, ["staff"])
        assert env.org_role(uid) == "Viewer"

    def test_new_user_provisioned_with_mapped_role(self, env):
        email = f"new-{uuid.uuid4().hex[:6]}@test.example"
        user = env.sign_in(email, env.config(env.rule("audit", "Auditor")), ["audit"])
        assert env.org_role(user.id) == "Auditor"

    def test_owner_never_changed(self, env):
        uid, email = env.user("Owner")
        cfg = env.config(env.rule("staff", "Viewer"), everyone_else="None")
        env.sign_in(email, cfg, ["staff"])
        assert env.org_role(uid) == "Owner"
        env.sign_in(email, cfg, [])
        assert env.org_role(uid) == "Owner"

    def test_unmapped_groups_keep_role(self, env):
        uid, email = env.user("Admin")
        env.sign_in(email, env.config(env.rule("x", "Viewer")), ["something-else"])
        assert env.org_role(uid) == "Admin"

    def test_missing_claim_counts_as_no_groups(self, env):
        uid, email = env.user("Admin")
        env.sign_in(email, env.config(env.rule("x", "Viewer"), everyone_else="Viewer"), None)
        assert env.org_role(uid) == "Viewer"

    def test_entra_overage_leaves_roles_alone(self, env):
        uid, email = env.user("Admin")
        cfg = env.config(env.rule("x", "Viewer"), everyone_else="None")
        env.sign_in(email, cfg, claims={"_claim_names": {"groups": "src1"}})
        assert env.org_role(uid) == "Admin"

    def test_disabled_mapping_does_nothing(self, env):
        uid, email = env.user("Member")
        cfg = env.config(env.rule("admins", "Admin"))
        cfg.role_mapping.enabled = False
        env.sign_in(email, cfg, ["admins"])
        assert env.org_role(uid) == "Member"

    def test_rbac_unavailable_does_nothing(self, env):
        uid, email = env.user("Member")
        auth_user = AuthUser(
            provider_type=AuthProviderType.OIDC,
            external_id="x",
            email=email,
            raw_data={"sub": "x", "email": email, "groups": ["admins"]},
        )
        with patch("rhesis.backend.app.features.FeatureRegistry.is_available", return_value=False):
            resolve_sso_user(env.db, auth_user, env.org, env.config(env.rule("admins", "Admin")))
        assert env.org_role(uid) == "Member"

    def test_custom_role(self, env):
        from tests.backend.ee.rbac._rbac_helpers import _custom_role

        custom = _custom_role(env.db, env.org_id, name="QA Lead", scope="organization", level=50)
        uid, email = env.user("Viewer")
        cfg = env.config(MappingRule(group="qa", role_id=custom.id))
        env.sign_in(email, cfg, ["qa"])
        assert env.org_role(uid) == "QA Lead"


class TestApplyMode:
    def test_on_create_skips_existing_users(self, env):
        uid, email = env.user("Member")
        env.sign_in(email, env.config(env.rule("x", "Viewer")), ["y"])  # Earlier SSO sign-in.
        env.sign_in(email, env.config(env.rule("admins", "Admin"), apply="on_create"), ["admins"])
        assert env.org_role(uid) == "Member"

    def test_on_create_sets_invited_users_at_first_sso_sign_in(self, env):
        uid, email = env.user("Member")  # Invited: account exists, no SSO sign-in yet.
        cfg = env.config(env.rule("admins", "Admin"), apply="on_create")
        env.sign_in(email, cfg, ["admins"])
        assert env.org_role(uid) == "Admin"
        env.sign_in(email, env.config(env.rule("admins", "Viewer"), apply="on_create"), ["admins"])
        assert env.org_role(uid) == "Admin"

    def test_on_create_sets_new_users(self, env):
        email = f"new-{uuid.uuid4().hex[:6]}@test.example"
        user = env.sign_in(email, env.config(env.rule("v", "Viewer"), apply="on_create"), ["v"])
        assert env.org_role(user.id) == "Viewer"


class TestBlock:
    def test_unknown_person_not_created(self, env):
        email = f"new-{uuid.uuid4().hex[:6]}@test.example"
        with pytest.raises(SSOLoginError) as exc:
            env.sign_in(email, env.config(env.rule("a", "Admin"), everyone_else="block"), ["b"])
        assert exc.value.reason_code == "no_matching_group"
        with bypass_tenant_filter():
            assert env.db.query(User).filter_by(email=email).first() is None

    def test_existing_member_blocked(self, env):
        _, email = env.user("Admin")
        with pytest.raises(SSOLoginError):
            env.sign_in(email, env.config(env.rule("a", "Admin"), everyone_else="block"), [])

    def test_owner_not_blocked(self, env):
        uid, email = env.user("Owner")
        env.sign_in(email, env.config(env.rule("a", "Admin"), everyone_else="block"), [])
        assert env.org_role(uid) == "Owner"

    def test_owner_keeps_project_memberships(self, env):
        uid, email = env.user("Owner")
        _add_project_member(env.db, env.org_id, env.support, uid, env.role["Admin"])
        cfg = env.config(env.rule("eng", support="Viewer"), everyone_else="block")
        env.sign_in(email, cfg, [])
        assert env.project_role(uid, env.support) == "Admin"
        env.sign_in(email, cfg, ["eng"])
        assert env.project_role(uid, env.support) == "Admin"

    def test_project_rule_match_is_not_blocked(self, env):
        uid, email = env.user("Member")
        cfg = env.config(env.rule("cl", support="Admin"), everyone_else="block")
        env.sign_in(email, cfg, ["cl"])
        assert env.project_role(uid, env.support) == "Admin"


class TestProjects:
    def test_enrolls_with_role(self, env):
        uid, email = env.user("Member")
        env.sign_in(email, env.config(env.rule("qa", support="Member")), ["qa"])
        assert env.project_role(uid, env.support) == "Member"
        assert env.project_role(uid, env.claims) is None

    def test_updates_role(self, env):
        uid, email = env.user("Member")
        _add_project_member(env.db, env.org_id, env.support, uid, env.role["Viewer"])
        env.sign_in(email, env.config(env.rule("qa", support="Admin")), ["qa"])
        assert env.project_role(uid, env.support) == "Admin"

    def test_removes_membership_when_group_lost(self, env):
        uid, email = env.user("Member")
        cfg = env.config(env.rule("qa", support="Member"))
        env.sign_in(email, cfg, ["qa"])
        env.sign_in(email, cfg, [])
        assert env.project_role(uid, env.support) is None

    def test_unmanaged_project_untouched(self, env):
        uid, email = env.user("Member")
        _add_project_member(env.db, env.org_id, env.claims, uid, env.role["Viewer"])
        env.sign_in(email, env.config(env.rule("qa", support="Member")), [])
        assert env.project_role(uid, env.claims) == "Viewer"

    def test_project_owner_not_removed(self, env):
        uid, email = env.user("Member")
        env.db.execute(
            text("UPDATE project SET owner_id = :u WHERE id = :p"),
            {"u": str(uid), "p": str(env.support)},
        )
        _add_project_member(env.db, env.org_id, env.support, uid)
        env.sign_in(email, env.config(env.rule("qa", support="Member")), [])
        assert env.project_role(uid, env.support) == "member"

    def test_project_owner_not_downgraded(self, env):
        uid, email = env.user("Member")
        env.db.execute(
            text("UPDATE project SET owner_id = :u WHERE id = :p"),
            {"u": str(uid), "p": str(env.support)},
        )
        _add_project_member(env.db, env.org_id, env.support, uid, env.role["Admin"])
        env.sign_in(email, env.config(env.rule("contractors", support="Viewer")), ["contractors"])
        assert env.project_role(uid, env.support) == "Admin"

    def test_deleted_project_ignored(self, env):
        uid, email = env.user("Member")
        ghost = uuid.uuid4()
        cfg = env.config(
            MappingRule(
                group="qa", projects=[ProjectGrant(project_id=ghost, role_id=env.role["Admin"])]
            )
        )
        env.sign_in(email, cfg, ["qa"])
        assert env.project_role(uid, ghost) is None

    def test_highest_project_role_wins(self, env):
        uid, email = env.user("Member")
        cfg = env.config(env.rule("a", support="Viewer"), env.rule("b", support="Admin"))
        env.sign_in(email, cfg, ["a", "b"])
        assert env.project_role(uid, env.support) == "Admin"


class TestSnapshot:
    def test_stored_even_without_mapping(self, env):
        uid, email = env.user("Member")
        cfg = env.config()
        cfg.role_mapping = None
        env.sign_in(email, cfg, ["qa"], claims={"realm_access": {"roles": ["r1"]}})
        snap = env.snapshot(uid)
        assert {"path": ["groups"], "values": ["qa"]} in snap
        assert {"path": ["realm_access", "roles"], "values": ["r1"]} in snap


class TestRevocation:
    """What the mapping gave is taken back once no rule gives it."""

    def test_leaving_the_only_group_removes_the_role(self, env):
        uid, email = env.user("Member")
        cfg = env.config(env.rule("admins", "Admin"))
        env.sign_in(email, cfg, ["admins"])
        env.sign_in(email, cfg, [])
        assert env.org_role(uid) == "None"

    def test_deleting_the_rule_removes_the_role(self, env):
        uid, email = env.user("Member")
        env.sign_in(email, env.config(env.rule("admins", "Admin")), ["admins"])
        env.sign_in(email, env.config(env.rule("other", "Viewer")), ["admins"])
        assert env.org_role(uid) == "None"

    def test_deleting_the_rule_removes_its_projects(self, env):
        uid, email = env.user("Member")
        env.sign_in(email, env.config(env.rule("qa", support="Admin")), ["qa"])
        env.sign_in(email, env.config(env.rule("other", "Viewer")), ["qa"])
        assert env.project_role(uid, env.support) is None

    def test_hand_granted_project_role_survives_rule_removal(self, env):
        uid, email = env.user("Member")
        env.sign_in(email, env.config(env.rule("qa", support="Admin")), ["qa"])
        _add_project_member(env.db, env.org_id, env.support, uid, env.role["Viewer"])
        env.sign_in(email, env.config(env.rule("other", "Viewer")), ["qa"])
        assert env.project_role(uid, env.support) == "Viewer"

    def test_role_from_fallback_is_not_taken_back(self, env):
        uid, email = env.user("Member")
        env.sign_in(email, env.config(env.rule("a", "Admin"), everyone_else="Viewer"), [])
        env.sign_in(email, env.config(env.rule("a", "Admin")), [])
        assert env.org_role(uid) == "Viewer"

    def test_role_never_given_by_mapping_is_kept(self, env):
        uid, email = env.user("Admin")
        env.sign_in(email, env.config(env.rule("a", "Viewer")), [])
        assert env.org_role(uid) == "Admin"

    def test_moving_between_groups_does_not_revoke(self, env):
        uid, email = env.user("Member")
        cfg = env.config(env.rule("admins", "Admin"), env.rule("staff", "Viewer"))
        env.sign_in(email, cfg, ["admins"])
        env.sign_in(email, cfg, ["staff"])
        assert env.org_role(uid) == "Viewer"

    def test_on_create_role_is_not_revoked(self, env):
        email = f"new-{uuid.uuid4().hex[:6]}@test.example"
        cfg = env.config(env.rule("a", "Admin"), apply="on_create")
        user = env.sign_in(email, cfg, ["a"])
        env.sign_in(email, cfg, [])
        assert env.org_role(user.id) == "Admin"


class TestStaleReferences:
    def test_deleted_custom_role_does_not_break_sign_in(self, env):
        from tests.backend.ee.rbac._rbac_helpers import _custom_role

        custom = _custom_role(env.db, env.org_id, name="Temp", scope="organization")
        cfg = env.config(MappingRule(group="qa", role_id=custom.id))
        env.db.delete(custom)
        env.db.flush()
        uid, email = env.user("Member")
        env.sign_in(email, cfg, ["qa"])
        assert env.org_role(uid) == "Member"

    def test_other_orgs_role_is_ignored(self, env):
        from tests.backend.ee.rbac._rbac_helpers import _custom_role

        other = _create_org(env.db)
        foreign = _custom_role(env.db, other, name="Foreign", scope="organization", level=90)
        from tests.backend.fixtures.rls import scope_to_org

        scope_to_org(env.db, env.org_id)
        uid, email = env.user("Member")
        env.sign_in(email, env.config(MappingRule(group="qa", role_id=foreign.id)), ["qa"])
        assert env.org_role(uid) == "Member"
