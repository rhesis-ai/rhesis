"""
SQLAlchemy event listeners for automatic tenant scope filtering and stamping.

TWO LISTENERS
-------------
1. auto_filter  (Session.do_orm_execute)
   Adds WHERE organization_id = ... (and project_id logic) to every SELECT, UPDATE,
   and DELETE issued through the Session: db.query(...), db.execute(select(...)),
   db.scalars(...), Query.update()/.delete(), and relationship lazy/eager loads.
   Uses with_loader_criteria() so the predicate follows an entity everywhere it
   occurs - joins, subqueries, aliases, and loader-triggered secondary queries -
   without needing to touch every call site.

2. auto_stamp  (Session.before_flush)
   Before every flush, fills organization_id / user_id / project_id from the ambient
   RequestScope on pending ORM objects when the column is present and the value is None.
   Bypass does NOT affect stamping.

COVERAGE NOTES
--------------
This used to run on Query.before_compile, which only fires for the legacy db.query(...)
API - db.execute(select(...)) went unfiltered at the ORM layer (RLS was the only
backstop for that path). do_orm_execute fires for every Session.execute() call,
including the internal one legacy Query.all()/.update()/.delete() issue under the
hood (Query has been built on the unified execution path since SQLAlchemy 1.4), so
one listener now covers all of it, plus relationship loads that before_compile could
not reach at all.

TENANT-SCOPED CLASSES
----------------------
The set of classes to filter is derived once, at listener-registration time, from
the actual mapped columns (has_organization_id / has_project_id in query_utils.py) -
not a hand-maintained per-model registry. A new model with an organization_id column
is covered automatically the next time the process starts; nobody has to remember to
add it anywhere. EXEMPT_TABLES is the one deliberate override: Token has a real
organization_id column but must stay queryable by its raw value before any scope is
known, so it is force-excluded despite otherwise matching. User and Organization
need no override - they are excluded because they lack the column outright (User's
organization_id is a plain FK, not something the identity lookup path filters on;
Organization has no such column since it's the org table itself). Keeping all three
in EXEMPT_TABLES matches the original design intent even though only Token is load
bearing today.

PRODUCTION KNOBS
----------------
RHESIS_DISABLE_SCOPE_LISTENER=1   Kill switch. Both filter and stamp are no-ops.
                                   For emergency rollback without redeploy.
                                   Scope ONLY of this switch: the ORM-layer
                                   auto_filter / auto_stamp listeners. It does NOT
                                   disable the PostgreSQL RLS GUCs (set in
                                   database.py + re-applied by _reapply_tenant_vars);
                                   RLS remains the security backstop regardless.

BYPASS
------
Admin / cross-org reads: bypass_tenant_filter() context manager (scope.py). Disables
auto_filter for its block; auto_stamp is unaffected.

KNOWN LIMITATIONS
-----------------
- Session.bulk_insert_mappings / bulk_save_objects skip before_flush; auto-stamp
  does NOT fire, and they also skip do_orm_execute, so auto-filter does not apply
  either. Payloads must include organization_id / user_id / project_id.
- Raw SQL INSERT/UPDATE/DELETE bypasses both listeners. Add explicit WHERE clauses
  or rely on RLS (Phase 5).
- Background scripts run outside get_db_with_tenant_variables; call bind_scope()
  explicitly before writing to tenant tables.
"""

import logging
import os

from sqlalchemy import and_, event, or_
from sqlalchemy.orm import Session, with_loader_criteria

logger = logging.getLogger(__name__)

# Tables force-excluded from auto_filter despite matching column presence.
# Rationale per table is in the module docstring (TENANT-SCOPED CLASSES) - Token
# is the only load-bearing entry; User/Organization are already excluded by
# column absence and are listed here defensively.
EXEMPT_TABLES = frozenset({"user", "organization", "token"})

# Tables exempt from the PROJECT predicate only (org filtering still applies).
#
# project_membership is the access-control join table: it must be queryable by
# org scope ALONE, before any project is resolved (e.g. get_project_context
# decides which project a user may use by reading this table, and the project
# switcher lists a user's memberships across ALL projects). Applying a project
# filter here would make membership invisible whenever the active project does
# not match, breaking project resolution. It carries org isolation only.
PROJECT_FILTER_EXEMPT_TABLES = frozenset({"project_membership"})

# Guard against duplicate listener registration (e.g. test reloads, hot-reload)
_listeners_registered: bool = False

# Key under which RequestScope is stored in Session.info (mirrors _SCOPE_KEY in database.py)
_SESSION_SCOPE_KEY = "_scope"


def _scope_from_session(session):
    """
    Read the active RequestScope preferring Session.info over ContextVar.

    Session.info is set by get_db_with_tenant_variables() and is visible to
    SQLAlchemy event listeners regardless of whether the caller is a sync or
    async route handler (no ContextVar thread-boundary issue).

    Falls back to the ContextVar for Celery tasks, background scripts, and any
    path that binds scope explicitly without going through a DB session.
    """
    from rhesis.backend.app.scope import current_scope

    scope = session.info.get(_SESSION_SCOPE_KEY)
    if scope is not None:
        return scope
    return current_scope()


def _kill_switch_active() -> bool:
    """Return True when RHESIS_DISABLE_SCOPE_LISTENER=1 is set."""
    return os.environ.get("RHESIS_DISABLE_SCOPE_LISTENER", "").lower() in ("1", "true")


def _build_tenant_classes():
    """
    Enumerate mapped classes needing the org/project WHERE predicate.

    Returns a list of (model_cls, needs_project_filter) tuples.
    """
    from rhesis.backend.app.models.base import Base
    from rhesis.backend.app.utils.query_utils import has_organization_id, has_project_id

    tenant_classes = []
    for mapper in Base.registry.mappers:
        model_cls = mapper.class_
        tablename = getattr(model_cls, "__tablename__", None)
        if tablename in EXEMPT_TABLES:
            continue
        if not has_organization_id(model_cls):
            continue
        needs_project_filter = (
            has_project_id(model_cls) and tablename not in PROJECT_FILTER_EXEMPT_TABLES
        )
        tenant_classes.append((model_cls, needs_project_filter))
    return tenant_classes


# ----------------------------------------------------------------------------
# Criteria builders for with_loader_criteria().
#
# Each returns a freshly defined, UNCONDITIONAL closure over plain scalar values
# (never a dataclass/dict looked up inside the closure body). SQLAlchemy's lambda
# cache keys on the closure's code object plus its captured values; a closure that
# branches on a mutable value's *shape* at call time (e.g. "if scope.project_id")
# risks serving a stale cached WHERE shape from an earlier call with a different
# branch. Picking one of these three fixed-shape functions in auto_filter, instead
# of branching inside a single shared closure, avoids that trap.
# ----------------------------------------------------------------------------


def _org_only_criteria(organization_id):
    def _criteria(cls):
        return cls.organization_id == organization_id

    return _criteria


def _org_and_active_project_criteria(organization_id, project_id):
    def _criteria(cls):
        return and_(
            cls.organization_id == organization_id,
            or_(cls.project_id == project_id, cls.project_id.is_(None)),
        )

    return _criteria


def _org_and_null_project_criteria(organization_id):
    def _criteria(cls):
        return and_(
            cls.organization_id == organization_id,
            cls.project_id.is_(None),
        )

    return _criteria


def setup_scope_listeners():
    """
    Register auto-filter and auto-stamp event listeners.

    Called once at import time from models/__init__.py.
    No-ops if RHESIS_DISABLE_SCOPE_LISTENER=1 is set or if already registered.
    """
    global _listeners_registered

    if _listeners_registered:
        return

    if _kill_switch_active():
        logger.warning(
            "Scope listeners DISABLED via RHESIS_DISABLE_SCOPE_LISTENER. "
            "Auto-filter and auto-stamp are inactive."
        )
        return

    tenant_classes = _build_tenant_classes()

    # Listener 1: auto_filter - see module docstring for what it covers.
    @event.listens_for(Session, "do_orm_execute")
    def auto_filter(orm_execute_state):
        from rhesis.backend.app.scope import is_tenant_filter_disabled

        if _kill_switch_active():
            return
        if is_tenant_filter_disabled():
            return

        # Deliberately does not skip is_column_load / is_relationship_load to rely on
        # with_loader_criteria's propagation instead: propagation only carries criteria
        # from whatever SELECT loaded the parent, so an object created via
        # session.add()+flush() (an INSERT, not a SELECT) would have its relationships
        # load unfiltered later. Re-attaching every time costs a redundant re-attach on
        # already-covered loads, not a correctness risk.
        scope = _scope_from_session(orm_execute_state.session)
        if scope.organization_id is None:
            return

        # Project filtering is fail-closed: we only reach this branch when an org
        # scope is active (the check above returns early when organization_id is
        # None, so org-less system/bootstrap sessions are never project-filtered).
        #   - project set   -> rows in that project plus org-level (NULL) rows
        #   - project unset -> org-level (NULL) rows only
        if scope.project_id:
            project_criteria = _org_and_active_project_criteria(
                scope.organization_id, scope.project_id
            )
        else:
            project_criteria = _org_and_null_project_criteria(scope.organization_id)
        org_only_criteria = _org_only_criteria(scope.organization_id)

        stmt = orm_execute_state.statement
        for model_cls, needs_project_filter in tenant_classes:
            criteria = project_criteria if needs_project_filter else org_only_criteria
            stmt = stmt.options(with_loader_criteria(model_cls, criteria, include_aliases=True))
        orm_execute_state.statement = stmt

    # Listener 2: auto_stamp - see module docstring for what it fills in.
    #
    # Uses Session.before_flush rather than the mapper-level before_insert because
    # declarative_base() does not propagate before_insert to subclasses correctly in
    # all SQLAlchemy 2.x configurations; before_flush gives direct access to
    # session.new and fires before the INSERT statements are issued.
    #
    # Base here is models.base.Base (the @as_declarative() one all app models
    # inherit from), not the declarative_base() Base in database.py.
    from rhesis.backend.app.models.base import Base

    @event.listens_for(Session, "before_flush")
    def auto_stamp(session, flush_context, instances):
        if _kill_switch_active():
            return

        # Prefer session.info for async-safe scope access (no ContextVar boundary issues).
        scope = _scope_from_session(session)
        if scope.organization_id is None and scope.user_id is None and scope.project_id is None:
            return  # Fast path: nothing to stamp

        for target in session.new:
            if not isinstance(target, Base):
                continue
            table = getattr(target, "__table__", None)
            if table is None:
                continue
            if table.name in EXEMPT_TABLES:
                continue
            col_names = frozenset(col.name for col in table.columns)

            if "organization_id" in col_names and getattr(target, "organization_id", None) is None:
                target.organization_id = scope.organization_id
            if "user_id" in col_names and getattr(target, "user_id", None) is None:
                target.user_id = scope.user_id
            if "project_id" in col_names and getattr(target, "project_id", None) is None:
                target.project_id = scope.project_id

    _listeners_registered = True
    logger.info("Scope event listeners registered (auto-filter + auto-stamp)")
