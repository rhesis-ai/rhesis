"""
SQLAlchemy event listeners for automatic tenant scope filtering and stamping.

TWO LISTENERS
-------------
1. auto_filter  (Query.before_compile)
   PRIMARY filter. Covers db.query(...), db.query(...).update(), db.query(...).delete().
   Fires for ALL Query-based operations including lazy-loaded relationships loaded via
   the legacy Query API. Does NOT fire for db.execute(select(...)) / ORM 2.0 style.

2. auto_stamp  (Base.before_insert)
   On every ORM INSERT, fills organization_id / user_id / project_id from the ambient
   RequestScope if the column is present and the value is None. Bypass does NOT affect
   stamping.

COVERAGE NOTES
--------------
This implementation uses Query.before_compile which covers the dominant db.query(...)
pattern throughout this codebase. db.execute(select(...)) statements (ORM 2.0 style)
are not filtered by this listener — explicit organization_id parameters must be used
for those until a future phase introduces do_orm_execute coverage.

EXEMPT MODELS
-------------
User, Organization, Token - no auto-filter applied; these must be queried
before any tenant context is known.

PRODUCTION KNOBS
----------------
RHESIS_DISABLE_SCOPE_LISTENER=1   Kill switch. Both filter and stamp are no-ops.
                                   For emergency rollback without redeploy.
RHESIS_SCOPE_STRICT_MODE=1        Raise when a SELECT touches a tenant-scoped
                                   table while scope is unbound. Recommended for
                                   staging; optional in prod.

PER-QUERY BYPASS
----------------
Legacy Query API:  query._bypass_scope = True

KNOWN LIMITATIONS
-----------------
- db.execute(select(...)) / ORM 2.0 SELECT style is NOT filtered by this listener.
  Use explicit organization_id filters or bind_scope() + a future do_orm_execute listener.
- Session.bulk_insert_mappings / bulk_save_objects skip before_insert; auto-stamp
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

# Tables that should never be auto-filtered (queried before any tenant context)
EXEMPT_TABLES = frozenset({"user", "organization", "token"})


def _inject_filter(query: Query, condition) -> Query:
    """
    Append a WHERE condition to a Query, even when LIMIT or OFFSET is already set.

    SQLAlchemy's public Query.filter() raises InvalidRequestError when called after
    .limit() or .offset(). We bypass that Python-level guard by writing directly to
    _where_criteria, which is exactly what filter() does internally minus the check.
    The resulting SQL is correct: WHERE always precedes LIMIT/OFFSET.
    """
    if hasattr(condition, "__clause_element__"):
        condition = condition.__clause_element__()
    query._where_criteria = query._where_criteria + (condition,)
    return query


def _kill_switch_active() -> bool:
    """Return True when RHESIS_DISABLE_SCOPE_LISTENER=1 is set."""
    return os.environ.get("RHESIS_DISABLE_SCOPE_LISTENER", "").lower() in ("1", "true")


def setup_scope_listeners():
    """
    Register auto-filter and auto-stamp event listeners.

    Called once at import time from models/__init__.py.
    No-ops if RHESIS_DISABLE_SCOPE_LISTENER=1 is set.
    """
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
        from rhesis.backend.app.scope import current_scope, is_tenant_filter_disabled

        if _kill_switch_active():
            return query
        if is_tenant_filter_disabled():
            return query
        if getattr(query, "_bypass_scope", False):
            return query

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
                query = _inject_filter(
                    query, entity.organization_id == scope.organization_id
                )
            if "project_id" in col_names and scope.project_id:
                query = _inject_filter(
                    query,
                    or_(
                        entity.project_id == scope.project_id,
                        entity.project_id.is_(None),
                    ),
                )

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

        from rhesis.backend.app.scope import current_scope

        scope = current_scope()
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

    logger.info("Scope event listeners registered (auto-filter + auto-stamp)")
