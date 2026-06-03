"""
SQLAlchemy event listeners for automatic tenant scope filtering and stamping.

TWO LISTENERS
-------------
1. auto_filter  (Query.before_compile)
   PRIMARY filter. Covers db.query(...), db.query(...).update(), db.query(...).delete().
   Fires for ALL Query-based operations including lazy-loaded relationships loaded via
   the legacy Query API. Does NOT fire for db.execute(select(...)) / ORM 2.0 style.

2. auto_stamp  (Session.before_flush)
   Before every flush, fills organization_id / user_id / project_id from the ambient
   RequestScope on pending ORM objects when the column is present and the value is None.
   Bypass does NOT affect stamping.

COVERAGE NOTES
--------------
This implementation uses Query.before_compile which covers the dominant db.query(...)
pattern throughout this codebase. db.execute(select(...)) statements (ORM 2.0 style)
are not filtered by this listener — use db.query(...) or add explicit organization_id
filters. RLS (Phase 5) backstops all tenant tables regardless of the filtering path.
If select()-style auto-filtering is ever needed, add a do_orm_execute listener here.

EXEMPT MODELS
-------------
User, Organization, Token - no auto-filter applied; these must be queried
before any tenant context is known.

PRODUCTION KNOBS
----------------
RHESIS_DISABLE_SCOPE_LISTENER=1   Kill switch. Both filter and stamp are no-ops.
                                   For emergency rollback without redeploy.
                                   Scope ONLY of this switch: the ORM-layer
                                   auto_filter / auto_stamp listeners. It does NOT
                                   disable the PostgreSQL RLS GUCs (set in
                                   database.py + re-applied by _reapply_tenant_vars);
                                   RLS remains the security backstop regardless.

PER-QUERY BYPASS
----------------
Legacy Query API:  query._bypass_scope = True

KNOWN LIMITATIONS
-----------------
- db.execute(select(...)) / ORM 2.0 SELECT style is NOT filtered by this listener.
  Use db.query(...) or explicit filters. RLS provides the security backstop.
- Session.bulk_insert_mappings / bulk_save_objects skip before_flush; auto-stamp
  does NOT fire. Payloads must include organization_id / user_id / project_id.
- Raw SQL INSERT/UPDATE/DELETE bypasses both listeners. Add explicit WHERE clauses
  or rely on RLS (Phase 5).
- Background scripts run outside get_db_with_tenant_variables; call bind_scope()
  explicitly before writing to tenant tables.
"""

import logging
import os

from sqlalchemy import event, or_
from sqlalchemy.orm import Query, Session

logger = logging.getLogger(__name__)

# Tables that should never be auto-filtered (queried before any tenant context).
#
# This is the ORM-layer exempt set and is deliberately NARROWER than the RLS-exempt
# set in the migrations ({token, user, organization, refresh_token, alembic_version}).
# The two serve different layers and are not required to match:
#   - This set: tables the ORM auto_filter/auto_stamp listeners skip because they are
#     queried before any tenant context exists (auth/identity lookups).
#   - RLS-exempt set: tables with no tenant policy at the database level.
# refresh_token / alembic_version are absent here only because they have no
# organization_id column, so the listeners already no-op on them. If you add a tenant
# column to an auth/infra table, reconcile both lists deliberately.
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


def _inject_filter(query: Query, condition) -> Query:
    """
    Append a WHERE condition to a Query, even when LIMIT or OFFSET is already set.

    SQLAlchemy's public Query.filter() raises InvalidRequestError when called after
    .limit() or .offset(). We use the supported enable_assertions(False) path to
    bypass that Python-level guard without touching private internals. The resulting
    SQL is correct: WHERE always precedes LIMIT/OFFSET in the generated statement.
    """
    return query.enable_assertions(False).filter(condition)


def _kill_switch_active() -> bool:
    """Return True when RHESIS_DISABLE_SCOPE_LISTENER=1 is set."""
    return os.environ.get("RHESIS_DISABLE_SCOPE_LISTENER", "").lower() in ("1", "true")


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

    # ------------------------------------------------------------------
    # Listener 1: Auto-filter via Query.before_compile
    # Covers db.query(...), db.query(...).update(), db.query(...).delete()
    # ------------------------------------------------------------------
    @event.listens_for(Query, "before_compile", retval=True)
    def auto_filter(query):
        from rhesis.backend.app.scope import is_tenant_filter_disabled

        if _kill_switch_active():
            return query
        if is_tenant_filter_disabled():
            return query
        if getattr(query, "_bypass_scope", False):
            return query
        # Idempotency guard: before_compile can fire more than once for the same
        # Query object (e.g. subquery compilation). Avoid appending duplicate
        # predicates. Pattern mirrors _soft_delete_filter_applied in soft_delete_events.py.
        if getattr(query, "_scope_filter_applied", False):
            return query

        # Prefer session.info so async route handlers (event-loop thread) see the
        # same scope as the sync dep (threadpool thread) that created the session.
        session = query.session
        if session is not None:
            scope = _scope_from_session(session)
        else:
            from rhesis.backend.app.scope import current_scope

            scope = current_scope()
        if scope.organization_id is None:
            return query

        for desc in query.column_descriptions:
            entity = desc.get("entity")
            if entity is None:
                continue
            if getattr(entity, "__tablename__", None) in EXEMPT_TABLES:
                continue
            table = getattr(entity, "__table__", None)
            if table is None:
                continue
            # Use frozenset of names to avoid triggering SQLAlchemy column operators
            col_names = frozenset(col.name for col in table.columns)
            if "organization_id" in col_names:
                query = _inject_filter(query, entity.organization_id == scope.organization_id)
            # Project filtering is fail-closed: we only reach this branch when an org
            # scope is active (the listener returns early when organization_id is None,
            # so org-less system/bootstrap sessions are never project-filtered).
            #   - project set   -> rows in that project plus org-level (NULL) rows
            #   - project unset -> org-level (NULL) rows only
            # project_membership is exempt (org-scoped access-control table).
            if (
                "project_id" in col_names
                and getattr(entity, "__tablename__", None)
                not in PROJECT_FILTER_EXEMPT_TABLES
            ):
                if scope.project_id:
                    query = _inject_filter(
                        query,
                        or_(
                            entity.project_id == scope.project_id,
                            entity.project_id.is_(None),
                        ),
                    )
                else:
                    query = _inject_filter(query, entity.project_id.is_(None))

        query._scope_filter_applied = True
        logger.debug(
            "scope auto-filter: org=%s project=%s",
            scope.organization_id,
            scope.project_id,
        )
        return query

    # ------------------------------------------------------------------
    # Listener 2: Auto-stamp on INSERT via Session.before_flush
    #
    # Session.before_flush is used instead of the mapper-level before_insert
    # because declarative_base() does not propagate before_insert to subclasses
    # correctly in all SQLAlchemy 2.x configurations. Session.before_flush
    # gives direct access to session.new (pending inserts) and fires
    # synchronously before the INSERT statements are issued.
    #
    # Fills organization_id / user_id / project_id from RequestScope
    # when the column is present and the value is None.
    # Bypass does NOT suppress stamping.
    #
    # NOTE: We import Base from models.base (the @as_declarative() Base), NOT
    # from database.py (the declarative_base() Base). All application models
    # inherit from models.base.Base.
    # ------------------------------------------------------------------
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
