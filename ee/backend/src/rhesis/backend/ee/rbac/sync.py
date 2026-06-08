"""Idempotent RBAC catalog sync — SP7.

:func:`sync_rbac_catalog` is called once per startup (registered as a
startup hook by the EE bootstrap).  It reconciles the ``permission`` table
against the live capability registry and re-seeds the five built-in roles.

Invariants
----------
- **Idempotent**: running twice produces the same DB state.
- **Fail-closed for custom roles**: new capabilities are never auto-granted
  to org-owned custom roles or tokens.  Only the five built-in roles are
  recomputed.
- **Never hard-deletes**: deprecated capabilities are flagged ``is_retired``
  so historical ``role_permission`` rows remain auditable.  Retired
  permissions are removed from built-in role assignments on the next sync.
- **Built-in role recompute**: built-in role → permission assignments are
  derived fresh from :func:`~rhesis.backend.ee.rbac.models.permissions_for_built_in_role`
  on every sync, so a newly added resource lands in the right roles
  automatically (plan §2.1).

Dependency direction: EE → core only.  No core module imports from here.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Stable 64-bit key for the transaction-scoped advisory lock that serializes
# concurrent catalog syncs.  Value is the ASCII bytes of ``"RBACSYNC"`` and
# fits in a signed bigint.  See :func:`sync_rbac_catalog` for why this matters.
_SYNC_ADVISORY_LOCK_KEY = 0x52424143_53594E43


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def sync_rbac_catalog(db: "Session") -> None:
    """Synchronise the permission catalog and reseed built-in roles.

    Steps (all within the caller's transaction):

    1. Fetch the live capability list from
       :func:`~rhesis.backend.app.auth.capabilities.get_all_capabilities`.
    2. Upsert ``permission`` rows for every active capability (insert new,
       clear ``is_retired`` on revived ones).
    3. Mark ``is_retired = True`` for capabilities no longer in the registry.
    4. Upsert the five built-in ``role`` rows (Owner/Admin/Member/Viewer/None)
       without touching their ``organization_id`` (always NULL).
    5. For each built-in role, **replace** its ``role_permission`` rows with
       the set derived from :func:`permissions_for_built_in_role` — retired
       permissions are excluded.
    6. Custom roles (``is_built_in = False``) are left completely untouched
       (fail-closed: new capabilities are not auto-granted).

    Concurrency
    -----------
    Every web worker runs this at startup, so without coordination two workers
    booting simultaneously would race: both read an empty catalog and both try
    to ``INSERT`` the same ``permission`` row, and the UNIQUE constraint on
    ``permission.name`` aborts the loser's transaction (and therefore its
    startup).  A transaction-scoped Postgres advisory lock serializes the
    workers — the second waits for the first to commit, then sees the catalog
    already populated and does a no-op reconcile.  The lock auto-releases when
    the caller's transaction ends.

    Args:
        db: Active SQLAlchemy session.  The caller owns the transaction;
            this function neither commits nor rolls back.
    """
    from sqlalchemy import text

    from rhesis.backend.app.auth.capabilities import get_all_capabilities
    from rhesis.backend.ee.rbac.models import (
        BUILT_IN_ROLE_LEVELS,
        BUILT_IN_ROLE_NAMES,
        SCOPE_ORGANIZATION,
        Permission,
        Role,
        RolePermission,
        capability_scope,
        permissions_for_built_in_role,
    )

    capabilities: list[str] = get_all_capabilities()
    cap_set = set(capabilities)

    if not cap_set:
        logger.warning(
            "sync_rbac_catalog: capability registry is empty — "
            "call register_capabilities(app) before the sync hook runs"
        )
        return

    # Serialize concurrent multi-worker syncs (see "Concurrency" above).  The
    # lock is held until the caller commits/rolls back; a second worker blocks
    # here, then proceeds once the first has populated the catalog.
    db.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": _SYNC_ADVISORY_LOCK_KEY},
    )

    logger.info("sync_rbac_catalog: syncing %d capabilities", len(cap_set))

    # ------------------------------------------------------------------
    # Step 1 — Upsert permission rows
    # ------------------------------------------------------------------
    existing_perms: dict[str, Permission] = {
        p.name: p for p in db.query(Permission).all()
    }

    for cap in cap_set:
        perm = existing_perms.get(cap)
        resource_type, _, action = cap.partition(":")
        scope = capability_scope(cap)
        display_name = _make_display_name(resource_type, action)

        if perm is None:
            perm = Permission(
                name=cap,
                display_name=display_name,
                resource_type=resource_type,
                action=action,
                scope=scope,
                is_retired=False,
            )
            db.add(perm)
            logger.debug("sync_rbac_catalog: insert permission %r", cap)
        else:
            # Keep metadata in sync; clear retirement flag if capability is back.
            if perm.is_retired:
                perm.is_retired = False
                logger.info("sync_rbac_catalog: revived retired permission %r", cap)
            perm.display_name = display_name
            perm.resource_type = resource_type
            perm.action = action
            perm.scope = scope

    # ------------------------------------------------------------------
    # Step 2 — Retire capabilities no longer in the registry
    # ------------------------------------------------------------------
    retired_count = 0
    for name, perm in existing_perms.items():
        if name not in cap_set and not perm.is_retired:
            perm.is_retired = True
            retired_count += 1
            logger.info("sync_rbac_catalog: retired permission %r", name)

    if retired_count:
        logger.info("sync_rbac_catalog: retired %d permission(s)", retired_count)

    # Flush so the Permission PKs are populated before we reference them below.
    db.flush()

    # Rebuild lookup after flush (PKs are now available for new rows).
    all_perms: dict[str, Permission] = {
        p.name: p for p in db.query(Permission).all()
    }
    active_perms: dict[str, Permission] = {
        name: p for name, p in all_perms.items() if not p.is_retired
    }

    # ------------------------------------------------------------------
    # Step 3 — Upsert built-in role rows
    # ------------------------------------------------------------------
    existing_roles: dict[str, Role] = {
        r.name: r
        for r in db.query(Role).filter_by(is_built_in=True).all()
    }

    for role_name in BUILT_IN_ROLE_NAMES:
        role = existing_roles.get(role_name)
        level = BUILT_IN_ROLE_LEVELS[role_name]

        if role is None:
            role = Role(
                name=role_name,
                display_name=role_name,
                scope=SCOPE_ORGANIZATION,
                level=level,
                is_built_in=True,
                organization_id=None,
            )
            db.add(role)
            logger.info("sync_rbac_catalog: created built-in role %r (level=%d)", role_name, level)
        else:
            role.display_name = role_name
            role.level = level
            role.is_built_in = True
            role.scope = SCOPE_ORGANIZATION
            role.organization_id = None

    db.flush()

    # Rebuild role lookup after flush.
    built_in_roles: dict[str, Role] = {
        r.name: r
        for r in db.query(Role).filter_by(is_built_in=True).all()
    }

    # ------------------------------------------------------------------
    # Step 4 — Recompute role_permission for each built-in role
    # ------------------------------------------------------------------
    for role_name in BUILT_IN_ROLE_NAMES:
        role = built_in_roles[role_name]

        # Desired permission names for this role (only active capabilities).
        desired_names: set[str] = permissions_for_built_in_role(role_name, list(cap_set))

        # Existing role_permission rows for this role.
        existing_rp: dict[str, RolePermission] = {
            rp.permission.name: rp
            for rp in (
                db.query(RolePermission)
                .filter_by(role_id=role.id)
                .join(Permission)
                .all()
            )
        }

        existing_names = set(existing_rp.keys())

        to_add = desired_names - existing_names
        to_remove = existing_names - desired_names

        for cap_name in to_add:
            perm = active_perms.get(cap_name)
            if perm is None:
                # Desired but retired/unknown — skip (fail-closed).
                continue
            db.add(RolePermission(role_id=role.id, permission_id=perm.id))

        for cap_name in to_remove:
            rp = existing_rp.get(cap_name)
            if rp is not None:
                db.delete(rp)

        if to_add or to_remove:
            logger.info(
                "sync_rbac_catalog: role %r — +%d/-%d permissions",
                role_name,
                len(to_add),
                len(to_remove),
            )

    db.flush()
    logger.info(
        "sync_rbac_catalog: complete — %d active capabilities, %d built-in roles",
        len(active_perms),
        len(built_in_roles),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_display_name(resource_type: str, action: str) -> str:
    """Convert ``resource_type`` + ``action`` to a human-readable label.

    Examples::

        _make_display_name("test_set", "read")   → "Read test sets"
        _make_display_name("organization", "update") → "Update organization"
    """
    resource_display = resource_type.replace("_", " ")
    # Pluralise simple resource names (not "organization", "sso", etc.)
    _plural_whitelist = {
        "test_set", "test", "test_configuration", "test_run", "test_result",
        "experiment", "endpoint", "metric", "model", "comment", "task", "file",
    }
    if resource_type in _plural_whitelist and not resource_display.endswith("s"):
        resource_display = resource_display + "s"
    return f"{action.capitalize()} {resource_display}"


__all__ = ["sync_rbac_catalog"]
