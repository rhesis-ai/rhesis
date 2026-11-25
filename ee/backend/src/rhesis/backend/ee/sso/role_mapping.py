"""SSO role mapping: IdP group claims to organization and project roles (#3189).

At sign-in the token's group claim decides the member's org role and the roles in the
projects a rule names. Modelled on Grafana's role sync: it runs at every sign-in, the
highest role wins when several groups match, and nothing outside the mapping is touched.
Owners are never changed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, FrozenSet, Iterable, List, Mapping, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.ee.sso.audit import SSOAuditEvent, audit_log
from rhesis.backend.ee.sso.schemas import ClaimPath, RoleMapping

logger = logging.getLogger(__name__)

#: Claims that are lists of strings but never groups.
_SNAPSHOT_SKIP = frozenset({"aud", "amr", "acr", "scope", "scp", "_claim_names", "_claim_sources"})
_SNAPSHOT_MAX_PATHS = 50
_SNAPSHOT_MAX_VALUES = 500
_SNAPSHOT_MAX_VALUE_LEN = 256
_SNAPSHOT_MAX_DEPTH = 3

OWNER_ROLE = "Owner"
NO_ACCESS_ROLE = "None"
FALLBACK_ROLES = ("Viewer", "None")


def claim_segments(path: ClaimPath) -> List[str]:
    return [path] if isinstance(path, str) else list(path)


def extract_claim_values(claims: Mapping[str, Any], path: ClaimPath) -> Optional[List[str]]:
    """The strings at ``path``, or None when the claim isn't there.

    A single string counts as a one-item list; non-string items are dropped.
    """
    node: Any = claims
    for segment in claim_segments(path):
        if not isinstance(node, Mapping) or segment not in node:
            return None
        node = node[segment]
    if isinstance(node, str):
        return [node]
    if isinstance(node, list):
        return [v for v in node if isinstance(v, str)]
    return None


def has_group_overage(claims: Mapping[str, Any], path: ClaimPath) -> bool:
    """Entra ID leaves ``groups`` out above 200 groups and points to Graph instead."""
    segments = claim_segments(path)
    names = claims.get("_claim_names")
    return (
        len(segments) == 1
        and segments[0] not in claims
        and isinstance(names, Mapping)
        and segments[0] in names
    )


def claims_snapshot(claims: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Every list-of-strings claim, as ``[{"path": [...], "values": [...]}]``, capped."""
    found: List[Dict[str, Any]] = []

    def walk(node: Mapping[str, Any], prefix: List[str]) -> None:
        for key, value in node.items():
            if len(found) >= _SNAPSHOT_MAX_PATHS:
                return
            if not prefix and key in _SNAPSHOT_SKIP:
                continue
            path = [*prefix, key]
            if isinstance(value, Mapping) and len(path) < _SNAPSHOT_MAX_DEPTH:
                walk(value, path)
            elif isinstance(value, list) and value and all(isinstance(v, str) for v in value):
                values = [v for v in value if len(v) <= _SNAPSHOT_MAX_VALUE_LEN]
                found.append({"path": path, "values": values[:_SNAPSHOT_MAX_VALUES]})

    walk(claims, [])
    return found


def snapshot_values(snapshot: Optional[Iterable[Mapping[str, Any]]], path: ClaimPath) -> List[str]:
    segments = claim_segments(path)
    for entry in snapshot or ():
        if list(entry.get("path", [])) == segments:
            return list(entry.get("values", []))
    return []


@dataclass(frozen=True)
class MappingDecision:
    """What a mapping says for one person's groups."""

    #: The org role to set; None leaves it alone.
    org_role_id: Optional[UUID]
    #: Project id to role id, for the managed projects the person qualifies for.
    project_roles: Dict[UUID, UUID] = field(default_factory=dict)
    #: Every project some rule names. Memberships outside this set are never touched.
    managed_projects: FrozenSet[UUID] = frozenset()
    blocked: bool = False
    #: The group that set the org role, for the Team tab and the audit line.
    org_role_group: Optional[str] = None
    matched_groups: tuple = ()


def decide(
    mapping: RoleMapping,
    groups: Iterable[str],
    levels: Mapping[UUID, int],
    fallback_role_ids: Mapping[str, UUID],
) -> MappingDecision:
    """Apply ``mapping`` to a person's ``groups``. Pure; ``levels`` ranks role ids."""
    group_set = set(groups)
    matched = [r for r in mapping.rules if r.group in group_set]
    managed = frozenset(p.project_id for r in mapping.rules for p in r.projects)

    best_rule = None
    for rule in matched:
        # Unknown ids (a role deleted after saving, or not this org's) grant nothing.
        if rule.role_id is None or rule.role_id not in levels:
            continue
        if best_rule is None or levels.get(rule.role_id, -1) > levels.get(best_rule.role_id, -1):
            best_rule = rule

    project_roles: Dict[UUID, UUID] = {}
    for rule in matched:
        for grant in rule.projects:
            if grant.role_id not in levels:
                continue
            current = project_roles.get(grant.project_id)
            if current is None or levels.get(grant.role_id, -1) > levels.get(current, -1):
                project_roles[grant.project_id] = grant.role_id

    org_role_id = best_rule.role_id if best_rule else None
    blocked = False
    if not matched:
        if mapping.everyone_else == "block":
            blocked = True
        elif mapping.everyone_else in FALLBACK_ROLES:
            org_role_id = fallback_role_ids.get(mapping.everyone_else)

    return MappingDecision(
        org_role_id=org_role_id,
        project_roles=project_roles,
        managed_projects=managed,
        blocked=blocked,
        org_role_group=best_rule.group if best_rule else None,
        matched_groups=tuple(r.group for r in matched),
    )


# ---------------------------------------------------------------------------
# Database side
# ---------------------------------------------------------------------------


def role_levels(db: Session, organization_id: UUID) -> Dict[UUID, int]:
    """Level of every role the org can use: built-in plus its custom roles."""
    from rhesis.backend.app.scope import bypass_tenant_filter
    from rhesis.backend.ee.rbac.models import Role

    with bypass_tenant_filter():
        rows = (
            db.query(Role.id, Role.level)
            .filter((Role.organization_id.is_(None)) | (Role.organization_id == organization_id))
            .all()
        )
    return {rid: level for rid, level in rows}


def built_in_role_ids(db: Session) -> Dict[str, UUID]:
    from rhesis.backend.app.scope import bypass_tenant_filter
    from rhesis.backend.ee.rbac.models import Role

    with bypass_tenant_filter():
        rows = db.query(Role.name, Role.id).filter(Role.is_built_in.is_(True)).all()
    return {name: rid for name, rid in rows}


def decide_for_claims(
    db: Session, organization_id: UUID, mapping: RoleMapping, claims: Mapping[str, Any]
) -> Optional[MappingDecision]:
    """The decision for a sign-in, or None when the groups can't be known.

    A missing claim counts as no groups (so the fallback applies); an Entra overage
    leaves everything alone, because the person may well be in mapped groups.
    """
    if has_group_overage(claims, mapping.claim):
        logger.warning(
            "SSO role mapping skipped for org %s: the IdP left groups out of the token "
            "(group overage)",
            organization_id,
        )
        return None
    groups = extract_claim_values(claims, mapping.claim) or []
    return decide(mapping, groups, role_levels(db, organization_id), built_in_role_ids(db))


def is_owner(db: Session, organization_id: UUID, user_id: UUID) -> bool:
    from rhesis.backend.ee.rbac.models import OrganizationMember, Role

    return (
        db.query(OrganizationMember)
        .join(Role, OrganizationMember.role_id == Role.id)
        .filter(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
            Role.name == OWNER_ROLE,
            Role.is_built_in.is_(True),
        )
        .first()
        is not None
    )


def store_claims_snapshot(
    db: Session, organization_id: UUID, user_id: UUID, claims: Mapping[str, Any]
) -> None:
    """Remember the person's list-valued claims, for suggestions and previews."""
    from rhesis.backend.ee.rbac.models import OrganizationMember

    member = (
        db.query(OrganizationMember)
        .filter_by(organization_id=organization_id, user_id=user_id)
        .first()
    )
    if member is None:
        return
    member.sso_claims = claims_snapshot(claims)
    member.sso_claims_at = datetime.now(timezone.utc)


def first_sso_sign_in(db: Session, organization_id: UUID, user_id: UUID) -> bool:
    """True until the member's first SSO sign-in is stored. Invited people count as new."""
    member = _member(db, organization_id, user_id)
    return member is None or member.sso_claims_at is None


def _member(db: Session, organization_id: UUID, user_id: UUID):
    from rhesis.backend.ee.rbac.models import OrganizationMember

    return (
        db.query(OrganizationMember)
        .filter_by(organization_id=organization_id, user_id=user_id)
        .first()
    )


def _grants(member) -> Dict[str, Any]:
    grants = (member.sso_grants if member is not None else None) or {}
    return {"org_role": grants.get("org_role"), "projects": dict(grants.get("projects") or {})}


def revoked_org_role(member, decision: MappingDecision, no_access_id: UUID) -> Optional[UUID]:
    """None-role id when the mapping gave the member's current role and no rule gives it now.

    Without this, leaving the only mapped group (or deleting its rule) would leave the
    role the mapping handed out in place for good.
    """
    granted = _grants(member)["org_role"]
    if decision.org_role_id is not None or decision.blocked or not granted:
        return None
    if member is None or str(member.role_id) != granted:
        return None  # Changed since, by someone else: not ours to take back.
    return no_access_id


def _apply_org_role(
    db: Session, organization_id: UUID, user_id: UUID, role_id: UUID
) -> Optional[tuple]:
    """Set the org role unless the member is an Owner. Returns (before, after) on change."""
    from rhesis.backend.ee.rbac import crud as rbac_crud

    member = _member(db, organization_id, user_id)
    if member is not None and member.role_id == role_id:
        return None
    if is_owner(db, organization_id, user_id):
        return None
    before = member.role_id if member is not None else None
    rbac_crud.set_org_member_role(
        db, member, organization_id=organization_id, user_id=user_id, role_id=role_id
    )
    return before, role_id


def _apply_project_roles(
    db: Session,
    organization_id: UUID,
    user_id: UUID,
    decision: MappingDecision,
    previous: Mapping[str, str],
) -> List[dict]:
    """Enroll, re-role or remove the person in each project the mapping touches.

    Projects a rule names follow the rules. Projects only granted earlier lose the
    membership if it still has the role the mapping gave.
    """
    from rhesis.backend.app.models.project import Project
    from rhesis.backend.app.models.project_membership import ProjectMembership
    from rhesis.backend.app.scope import bypass_tenant_filter
    from rhesis.backend.app.services.project_membership import (
        ProjectServiceError,
        enroll_user_in_project,
        unenroll_user_from_project,
    )

    earlier = {UUID(pid): UUID(rid) for pid, rid in previous.items()}
    touched = set(decision.managed_projects) | set(earlier)
    if not touched:
        return []
    with bypass_tenant_filter():
        # A project's owner keeps their membership as it is.
        live = {
            pid
            for (pid, owner_id) in db.query(Project.id, Project.owner_id).filter(
                Project.organization_id == organization_id, Project.id.in_(touched)
            )
            if owner_id != user_id
        }
        memberships = {
            m.project_id: m
            for m in db.query(ProjectMembership).filter(
                ProjectMembership.organization_id == organization_id,
                ProjectMembership.user_id == user_id,
                ProjectMembership.project_id.in_(live),
            )
        }

    changes: List[dict] = []
    for project_id in sorted(live, key=str):
        want = decision.project_roles.get(project_id)
        current = memberships.get(project_id)
        if want is not None and current is None:
            enroll_user_in_project(db, user_id, project_id, organization_id, role_id=want)
            changes.append({"project_id": str(project_id), "before": None, "after": str(want)})
        elif want is not None and current.role_id != want:
            changes.append(
                {"project_id": str(project_id), "before": str(current.role_id), "after": str(want)}
            )
            current.role_id = want
        elif want is None and current is not None:
            named = project_id in decision.managed_projects
            if not named and current.role_id != earlier.get(project_id):
                continue  # Granted by hand since: leave it.
            try:
                unenroll_user_from_project(db, user_id, project_id, organization_id)
            except ProjectServiceError:
                continue
            before = str(current.role_id) if current.role_id else None
            changes.append({"project_id": str(project_id), "before": before, "after": None})
    db.flush()
    return changes


def _bust_permissions(user_id: UUID, organization_id: UUID) -> None:
    try:
        from rhesis.backend.app.services.permission_cache import get_permission_cache

        get_permission_cache().bust_user(user_id, organization_id)
    except Exception as exc:  # A failed bust falls back to the cache TTL.
        logger.warning("SSO role mapping: permission cache bust failed: %s", exc)


def apply_decision(
    db: Session, organization_id: UUID, user_id: UUID, decision: MappingDecision
) -> None:
    """Write the decision for one person and log what changed. Never commits.

    Owners are left alone, org role and project memberships alike.
    """
    if is_owner(db, organization_id, user_id):
        return
    member = _member(db, organization_id, user_id)
    previous = _grants(member)
    target = decision.org_role_id or revoked_org_role(
        member, decision, built_in_role_ids(db)[NO_ACCESS_ROLE]
    )
    org_change = _apply_org_role(db, organization_id, user_id, target) if target else None
    project_changes = _apply_project_roles(
        db, organization_id, user_id, decision, previous["projects"]
    )

    member = member or _member(db, organization_id, user_id)
    if member is not None:
        # Only roles from rules are remembered; fallback roles are never taken back.
        from_rule = decision.org_role_group is not None
        member.sso_grants = {
            "org_role": str(decision.org_role_id) if from_rule else None,
            "projects": {str(p): str(r) for p, r in decision.project_roles.items()},
        }
    if not org_change and not project_changes:
        return

    _bust_permissions(user_id, organization_id)
    details: Dict[str, Any] = {"groups": list(decision.matched_groups)}
    if org_change:
        before, after = org_change
        details["org_role"] = {"before": str(before) if before else None, "after": str(after)}
    if project_changes:
        details["projects"] = project_changes
    audit_log(
        SSOAuditEvent.ROLES_SYNCED, str(organization_id), actor_id=str(user_id), details=details
    )


# ---------------------------------------------------------------------------
# Admin side: save checks, seen groups, preview
# ---------------------------------------------------------------------------


class RoleMappingInvalid(ValueError):
    """A mapping that names a role or project the org can't use that way."""


def _usable_roles(db: Session, organization_id: UUID) -> Dict[UUID, Any]:
    from rhesis.backend.app.scope import bypass_tenant_filter
    from rhesis.backend.ee.rbac.models import Role

    with bypass_tenant_filter():
        rows = (
            db.query(Role)
            .filter((Role.organization_id.is_(None)) | (Role.organization_id == organization_id))
            .all()
        )
    return {r.id: r for r in rows}


def _live_project_ids(db: Session, organization_id: UUID, ids: Iterable[UUID]) -> set:
    from rhesis.backend.app.models.project import Project
    from rhesis.backend.app.scope import bypass_tenant_filter

    wanted = list(set(ids))
    if not wanted:
        return set()
    with bypass_tenant_filter():
        return {
            pid
            for (pid,) in db.query(Project.id).filter(
                Project.organization_id == organization_id, Project.id.in_(wanted)
            )
        }


def validate_mapping_refs(db: Session, organization_id: UUID, mapping: RoleMapping) -> None:
    """Check every role and project a mapping names. Raises RoleMappingInvalid."""
    from rhesis.backend.ee.rbac.models import ORG_ONLY_BUILT_IN_ROLES, SCOPE_ORGANIZATION

    roles = _usable_roles(db, organization_id)
    live = _live_project_ids(
        db, organization_id, (p.project_id for r in mapping.rules for p in r.projects)
    )
    for rule in mapping.rules:
        where = f"Group {rule.group!r}"
        if rule.role_id is not None:
            role = roles.get(rule.role_id)
            if role is None:
                raise RoleMappingInvalid(f"{where}: unknown role")
            if role.is_built_in and role.name == OWNER_ROLE:
                raise RoleMappingInvalid(f"{where}: Owner can't be given through SSO")
            if role.scope != SCOPE_ORGANIZATION:
                raise RoleMappingInvalid(f"{where}: {role.name} is a project-only role")
        for grant in rule.projects:
            if grant.project_id not in live:
                raise RoleMappingInvalid(f"{where}: unknown project")
            role = roles.get(grant.role_id)
            if role is None:
                raise RoleMappingInvalid(f"{where}: unknown project role")
            if role.is_built_in and (
                role.name == OWNER_ROLE or role.level == 0 or role.name in ORG_ONLY_BUILT_IN_ROLES
            ):
                raise RoleMappingInvalid(
                    f"{where}: {role.name} can't be given in a project through SSO"
                )


def _members_with_snapshots(db: Session, organization_id: UUID) -> List[Any]:
    from rhesis.backend.app.models.user import User
    from rhesis.backend.app.scope import bypass_tenant_filter
    from rhesis.backend.ee.rbac.models import OrganizationMember

    with bypass_tenant_filter():
        return (
            db.query(OrganizationMember, User)
            .join(User, User.id == OrganizationMember.user_id)
            .filter(
                OrganizationMember.organization_id == organization_id,
                User.organization_id == organization_id,
            )
            .all()
        )


def seen_claims(db: Session, organization_id: UUID, path: ClaimPath) -> Dict[str, Any]:
    """Values members signed in with for ``path``, and every list claim path seen."""
    counts: Dict[str, int] = {}
    paths: Dict[str, List[str]] = {}
    for member, _user in _members_with_snapshots(db, organization_id):
        if not member.sso_claims:
            continue
        for entry in member.sso_claims:
            key = "\x1f".join(entry.get("path", []))
            paths.setdefault(key, list(entry.get("path", [])))
        for value in set(snapshot_values(member.sso_claims, path)):
            counts[value] = counts.get(value, 0) + 1
    return {
        "groups": [
            {"value": v, "members": n}
            for v, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "claims": sorted(paths.values()),
    }


def preview_mapping(db: Session, organization_id: UUID, mapping: RoleMapping) -> Dict[str, Any]:
    """Who the mapping changes at their next sign-in, from their last sign-in's claims.

    Covers org roles; people with no stored claims yet are counted, not guessed. When
    the mapping runs only for new accounts, existing members never change.
    """
    if mapping.apply == "on_create":
        return {"changes": [], "without_sign_in": 0, "new_accounts_only": True}
    levels = role_levels(db, organization_id)
    builtins = built_in_role_ids(db)
    roles = _usable_roles(db, organization_id)
    changes: List[Dict[str, Any]] = []
    unknown = 0
    for member, user in _members_with_snapshots(db, organization_id):
        current = roles.get(member.role_id)
        if current is not None and current.is_built_in and current.name == OWNER_ROLE:
            continue
        if member.sso_claims is None:
            unknown += 1
            continue
        groups = snapshot_values(member.sso_claims, mapping.claim)
        decision = decide(mapping, groups, levels, builtins)
        target = decision.org_role_id or revoked_org_role(
            member, decision, builtins[NO_ACCESS_ROLE]
        )
        if decision.blocked:
            after_name, less = None, True
        elif target is None or target == member.role_id:
            continue
        else:
            after = roles.get(target)
            after_name = after.name if after else None
            less = levels.get(target, 0) < levels.get(member.role_id, 0)
        changes.append(
            {
                "user_id": str(user.id),
                "name": user.name or user.email,
                "email": user.email,
                "from_role": current.name if current else None,
                "to_role": after_name,
                "blocked": decision.blocked,
                "less_access": less,
            }
        )
    changes.sort(key=lambda c: (not c["less_access"], c["name"] or ""))
    return {"changes": changes, "without_sign_in": unknown, "new_accounts_only": False}


def managed_member_groups(
    db: Session, organization_id: UUID, mapping: Optional[RoleMapping]
) -> Dict[UUID, str]:
    """Members whose org role the mapping sets at every sign-in, with the deciding group.

    Owners and people not yet seen at an SSO sign-in are left out.
    """
    if mapping is None or not mapping.enabled or mapping.apply != "every_sign_in":
        return {}
    levels = role_levels(db, organization_id)
    builtins = built_in_role_ids(db)
    owner_id = builtins.get(OWNER_ROLE)
    managed: Dict[UUID, str] = {}
    for member, user in _members_with_snapshots(db, organization_id):
        if member.sso_claims is None or member.role_id == owner_id:
            continue
        decision = decide(
            mapping, snapshot_values(member.sso_claims, mapping.claim), levels, builtins
        )
        if decision.org_role_group:
            managed[user.id] = decision.org_role_group
        elif decision.org_role_id is not None:
            managed[user.id] = ""  # Set by the "everyone else" fallback.
    return managed


def _stored_sync_mapping(db: Session, organization_id: UUID) -> Optional[RoleMapping]:
    """The org's stored mapping when SSO is on and it applies at every sign-in."""
    from rhesis.backend.app.models.organization import Organization
    from rhesis.backend.app.scope import bypass_tenant_filter

    with bypass_tenant_filter():
        org = db.query(Organization).filter_by(id=organization_id).first()
    cfg = (org.sso_config or {}) if org is not None else {}
    if not cfg.get("enabled") or not cfg.get("role_mapping"):
        return None
    try:
        mapping = RoleMapping.model_validate(cfg["role_mapping"])
    except ValueError:
        logger.warning("Stored SSO role mapping for org %s is invalid", organization_id)
        return None
    if not mapping.enabled or mapping.apply != "every_sign_in":
        return None
    return mapping


def sso_managed_members(db: Session, organization_id: UUID) -> Dict[UUID, str]:
    """``managed_member_groups`` for the org's stored SSO config, when SSO is on."""
    mapping = _stored_sync_mapping(db, organization_id)
    return managed_member_groups(db, organization_id, mapping) if mapping else {}


def sso_manages_project_role(
    db: Session, organization_id: UUID, user_id: UUID, project_id: UUID
) -> bool:
    """Whether the mapping resets this person's role in this project at each sign-in."""
    mapping = _stored_sync_mapping(db, organization_id)
    if mapping is None or not any(
        p.project_id == project_id for r in mapping.rules for p in r.projects
    ):
        return False
    member = _member(db, organization_id, user_id)
    if member is None or member.sso_claims is None or is_owner(db, organization_id, user_id):
        return False
    from rhesis.backend.app.models.project import Project

    project = db.query(Project).filter_by(id=project_id).first()
    return project is not None and project.owner_id != user_id


__all__ = [
    "MappingDecision",
    "RoleMappingInvalid",
    "managed_member_groups",
    "preview_mapping",
    "seen_claims",
    "sso_managed_members",
    "sso_manages_project_role",
    "first_sso_sign_in",
    "validate_mapping_refs",
    "apply_decision",
    "claims_snapshot",
    "decide",
    "decide_for_claims",
    "extract_claim_values",
    "has_group_overage",
    "is_owner",
    "snapshot_values",
    "store_claims_snapshot",
]
