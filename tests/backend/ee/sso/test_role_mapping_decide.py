"""SSO role mapping: claim extraction, snapshot and the pure decision (#3189)."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from rhesis.backend.ee.sso.role_mapping import (
    claims_snapshot,
    decide,
    extract_claim_values,
    has_group_overage,
    snapshot_values,
)
from rhesis.backend.ee.sso.schemas import MappingRule, ProjectGrant, RoleMapping

ADMIN, AUDITOR, MEMBER, VIEWER, NONE, CUSTOM = (uuid4() for _ in range(6))
LEVELS = {ADMIN: 80, AUDITOR: 70, MEMBER: 60, CUSTOM: 50, VIEWER: 40, NONE: 0}
FALLBACKS = {"Viewer": VIEWER, "None": NONE}
SUPPORT, CLAIMS = uuid4(), uuid4()


def _mapping(*rules, **kw) -> RoleMapping:
    return RoleMapping(enabled=True, rules=list(rules), **kw)


def _rule(group, role=None, **projects) -> MappingRule:
    return MappingRule(
        group=group,
        role_id=role,
        projects=[ProjectGrant(project_id=p, role_id=r) for p, r in projects.values()],
    )


class TestExtractClaimValues:
    def test_list(self):
        assert extract_claim_values({"groups": ["a", "b"]}, "groups") == ["a", "b"]

    def test_single_string_is_one_group(self):
        assert extract_claim_values({"groups": "a"}, "groups") == ["a"]

    def test_nested_path(self):
        claims = {"realm_access": {"roles": ["admin"]}}
        assert extract_claim_values(claims, ["realm_access", "roles"]) == ["admin"]

    def test_url_claim_name_is_not_split_on_dots(self):
        claims = {"https://acme.com/groups": ["x"]}
        assert extract_claim_values(claims, "https://acme.com/groups") == ["x"]

    def test_missing_claim(self):
        assert extract_claim_values({}, "groups") is None
        assert extract_claim_values({"realm_access": "x"}, ["realm_access", "roles"]) is None

    def test_non_strings_dropped(self):
        assert extract_claim_values({"groups": ["a", 1, None, {"b": 1}]}, "groups") == ["a"]

    def test_wrong_type(self):
        assert extract_claim_values({"groups": 5}, "groups") is None


class TestOverage:
    def test_entra_overage(self):
        claims = {"_claim_names": {"groups": "src1"}, "_claim_sources": {"src1": {}}}
        assert has_group_overage(claims, "groups")

    def test_no_overage_when_groups_present(self):
        assert not has_group_overage({"groups": [], "_claim_names": {"groups": "s"}}, "groups")

    def test_no_overage_without_claim_names(self):
        assert not has_group_overage({}, "groups")


class TestSnapshot:
    def test_keeps_list_claims_and_nested_roles(self):
        claims = {
            "sub": "1",
            "email": "a@b.c",
            "aud": ["rhesis"],
            "groups": ["eval-admins"],
            "realm_access": {"roles": ["offline_access"]},
            "resource_access": {"rhesis": {"roles": ["rhesis-user"]}},
        }
        snap = claims_snapshot(claims)
        assert snapshot_values(snap, "groups") == ["eval-admins"]
        assert snapshot_values(snap, ["realm_access", "roles"]) == ["offline_access"]
        assert snapshot_values(snap, ["resource_access", "rhesis", "roles"]) == ["rhesis-user"]
        assert snapshot_values(snap, "aud") == []

    def test_caps_size(self):
        claims = {f"c{i}": [f"v{j}" for j in range(1000)] for i in range(80)}
        claims["long"] = ["x" * 1000]
        snap = claims_snapshot(claims)
        assert len(snap) <= 50
        assert all(len(e["values"]) <= 500 for e in snap)

    def test_long_values_dropped(self):
        assert snapshot_values(claims_snapshot({"g": ["x" * 300, "ok"]}), "g") == ["ok"]


class TestDecide:
    def test_highest_org_role_wins(self):
        m = _mapping(_rule("staff", VIEWER), _rule("admins", ADMIN), _rule("qa", MEMBER))
        d = decide(m, ["staff", "qa", "admins"], LEVELS, FALLBACKS)
        assert d.org_role_id == ADMIN
        assert d.org_role_group == "admins"

    def test_rule_order_does_not_matter(self):
        a = decide(_mapping(_rule("x", MEMBER), _rule("y", ADMIN)), ["x", "y"], LEVELS, FALLBACKS)
        b = decide(_mapping(_rule("y", ADMIN), _rule("x", MEMBER)), ["x", "y"], LEVELS, FALLBACKS)
        assert a.org_role_id == b.org_role_id == ADMIN

    def test_project_highest_role_wins(self):
        m = _mapping(
            _rule("qa", MEMBER, p=(SUPPORT, VIEWER)),
            _rule("leads", None, p=(SUPPORT, ADMIN)),
        )
        d = decide(m, ["qa", "leads"], LEVELS, FALLBACKS)
        assert d.project_roles == {SUPPORT: ADMIN}
        assert d.org_role_id == MEMBER

    def test_managed_projects_cover_every_rule(self):
        m = _mapping(_rule("qa", None, p=(SUPPORT, MEMBER)), _rule("cl", None, p=(CLAIMS, ADMIN)))
        d = decide(m, ["qa"], LEVELS, FALLBACKS)
        assert d.managed_projects == {SUPPORT, CLAIMS}
        assert d.project_roles == {SUPPORT: MEMBER}

    def test_project_only_rule_leaves_org_role(self):
        d = decide(_mapping(_rule("cl", None, p=(CLAIMS, ADMIN))), ["cl"], LEVELS, FALLBACKS)
        assert d.org_role_id is None

    def test_group_match_is_exact(self):
        d = decide(_mapping(_rule("Admins", ADMIN)), ["admins", " Admins"], LEVELS, FALLBACKS)
        assert d.org_role_id is None
        assert d.matched_groups == ()

    @pytest.mark.parametrize(
        "fallback,expected,blocked",
        [
            ("keep", None, False),
            ("Viewer", VIEWER, False),
            ("None", NONE, False),
            ("block", None, True),
        ],
    )
    def test_everyone_else(self, fallback, expected, blocked):
        m = _mapping(_rule("admins", ADMIN), everyone_else=fallback)
        d = decide(m, ["unrelated"], LEVELS, FALLBACKS)
        assert d.org_role_id == expected
        assert d.blocked is blocked

    def test_fallback_not_used_when_a_project_rule_matches(self):
        m = _mapping(_rule("cl", None, p=(CLAIMS, ADMIN)), everyone_else="block")
        d = decide(m, ["cl"], LEVELS, FALLBACKS)
        assert not d.blocked

    def test_unknown_role_level_ranks_lowest(self):
        ghost = uuid4()
        d = decide(_mapping(_rule("a", ghost), _rule("b", VIEWER)), ["a", "b"], LEVELS, FALLBACKS)
        assert d.org_role_id == VIEWER


class TestSchema:
    def test_duplicate_groups_rejected(self):
        with pytest.raises(ValidationError, match="once"):
            _mapping(_rule("a", ADMIN), _rule("a", MEMBER))

    def test_rule_must_grant_something(self):
        with pytest.raises(ValidationError, match="needs"):
            MappingRule(group="a")

    def test_same_project_twice_rejected(self):
        with pytest.raises(ValidationError, match="twice"):
            MappingRule(
                group="a",
                projects=[
                    ProjectGrant(project_id=SUPPORT, role_id=MEMBER),
                    ProjectGrant(project_id=SUPPORT, role_id=ADMIN),
                ],
            )

    @pytest.mark.parametrize("claim", ["", [], ["a", ""], ["a", "b", "c", "d", "e"], "  "])
    def test_bad_claims(self, claim):
        with pytest.raises(ValidationError):
            RoleMapping(claim=claim)

    def test_rule_limit(self):
        with pytest.raises(ValidationError):
            RoleMapping(rules=[MappingRule(group=f"g{i}", role_id=ADMIN) for i in range(201)])

    def test_empty_group_rejected(self):
        with pytest.raises(ValidationError):
            MappingRule(group="", role_id=ADMIN)

    def test_unknown_fallback_rejected(self):
        with pytest.raises(ValidationError):
            RoleMapping(everyone_else="Owner")
