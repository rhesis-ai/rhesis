import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Generator, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from rhesis.backend.app.config.settings import get_database_settings

logger = logging.getLogger(__name__)


_TENANT_VARS_KEY = "_tenant_vars"
_SCOPE_KEY = "_scope"  # RequestScope stored on Session.info for async-safe access

_SET_CONFIG_SQL = text("""
    SELECT
        set_config('app.current_organization', :org_id, true),
        set_config('app.current_user', :user_id, true),
        set_config('app.current_project', :project_id, true)
""")


def _scope_to_guc_params(scope) -> dict:
    """Convert a RequestScope into the parameter dict for _SET_CONFIG_SQL.

    None values become empty strings: NULLIF(...) in the RLS policies treats an
    empty GUC as "no scope set" (migration / background-job passthrough).
    """
    return {
        "org_id": scope.organization_id or "",
        "user_id": scope.user_id or "",
        "project_id": scope.project_id or "",
    }


def _execute_set_config(executor, params: dict) -> None:
    """Run set_config for the tenant GUCs, tolerating missing-parameter errors.

    ``executor`` is either a Session (request/side-channel path) or a Connection
    (the after_begin re-apply path); both expose ``.execute``.
    """
    try:
        executor.execute(_SET_CONFIG_SQL, params)
    except Exception as e:
        logger.debug(f"Session variables set with potential creation: {e}")
        if "unrecognized configuration parameter" not in str(e).lower():
            raise


def _set_session_variables(
    db: Session, organization_id: str = "", user_id: str = "", project_id: str = ""
):
    """
    Set PostgreSQL session variables from raw id strings (side-channel / reset path).

    Always executes the SET call — the cost of a single ``set_config``
    round-trip is negligible compared to any query that follows.

    Uses is_local=true (transaction-scoped). Variables survive within a
    transaction but are cleared by db.commit(). The Session.after_begin
    listener (_reapply_tenant_vars) re-applies them at the start of every
    new transaction so that mid-request commits do not break RLS.

    This path records a plain params dict under ``_TENANT_VARS_KEY`` and does
    NOT store a RequestScope, so the ORM auto-filter / auto-stamp listeners stay
    inactive for callers using it directly (the documented side-channel
    behavior). The request/task path uses ``get_db_with_tenant_variables`` /
    ``_apply_scope_variables`` instead, which stores a single RequestScope.

    Args:
        db: SQLAlchemy session
        organization_id: Organization ID (defaults to empty string)
        user_id: User ID (defaults to empty string)
        project_id: Project ID (defaults to empty string)
    """
    params = {"org_id": organization_id, "user_id": user_id, "project_id": project_id}
    # Persist in session.info so after_begin can re-apply after each commit.
    db.info[_TENANT_VARS_KEY] = params
    _execute_set_config(db, params)
    logger.debug(
        f"Session variables set: org={organization_id}, user={user_id}, project={project_id}"
    )


def _apply_scope_variables(db: Session, scope) -> None:
    """Apply the RLS GUCs from a RequestScope without storing a separate dict.

    Used by the request/task path. The scope itself lives under ``_SCOPE_KEY``
    and is the single source the after_begin listener re-applies from, so no
    parallel ``_TENANT_VARS_KEY`` dict is needed here.
    """
    _execute_set_config(db, _scope_to_guc_params(scope))


def bind_scope_to_session(
    db: Session,
    organization_id: str = "",
    user_id: str = "",
    project_id: str = "",
) -> None:
    """Bind a full RequestScope (org, user, project) onto an existing session.

    Use this for **long-lived tenant sessions** — Celery tasks, WebSocket handlers,
    or any side-channel caller that owns a session for its entire lifetime and cannot
    wrap the work in ``get_db_with_tenant_variables``. It stores the RequestScope on
    ``Session.info['_scope']``, activating BOTH enforcement layers:

    - RLS GUCs (``app.current_organization`` / ``app.current_project``) — database-level
    - ORM auto-filter / auto-stamp listeners — SQLAlchemy-level

    Because ``_scope`` persists on the session, both layers remain active for the
    session's full lifetime and survive mid-request ``db.commit()`` calls.

    Do NOT use this for temporary project-scope windows inside a request (e.g. during
    onboarding where you shift to a project scope for one insert then return to
    org-level). The persisted ``_scope`` will leak into all subsequent queries on the
    same session. Use ``temporary_project_scope`` instead.
    """
    from rhesis.backend.app.scope import RequestScope

    scope = RequestScope(
        organization_id=organization_id or None,
        user_id=user_id or None,
        project_id=project_id or None,
    )
    db.info[_SCOPE_KEY] = scope
    _apply_scope_variables(db, scope)


@event.listens_for(Session, "after_begin")
def _reapply_tenant_vars(session: Session, transaction, connection) -> None:
    """
    Re-apply RLS GUCs at the start of every new transaction.

    set_config(..., is_local=true) is transaction-scoped: values are cleared
    when a transaction ends (commit or rollback). This listener re-applies
    the stored tenant vars so that code that calls db.commit() mid-request
    (e.g. Celery tasks, nested CRUD helpers) continues to be RLS-filtered
    on subsequent queries within the same session.

    Source of truth: the RequestScope under ``_SCOPE_KEY`` (request/task path),
    falling back to the ``_TENANT_VARS_KEY`` dict (side-channel callers that go
    through ``_set_session_variables`` directly).

    NOTE: This is intentionally NOT gated by RHESIS_DISABLE_SCOPE_LISTENER. That
    kill switch disables only the ORM-layer auto-filter/auto-stamp listeners; the
    RLS GUCs are the database-level security backstop and must keep being applied
    even when the ORM listeners are turned off. Disabling them would weaken, not
    relax, tenant isolation.
    """
    scope = session.info.get(_SCOPE_KEY)
    if scope is not None:
        params = _scope_to_guc_params(scope)
    else:
        params = session.info.get(_TENANT_VARS_KEY)
    if not params:
        return
    try:
        connection.execute(_SET_CONFIG_SQL, params)
    except Exception as e:
        logger.debug(f"_reapply_tenant_vars failed (non-fatal): {e}")


def get_database_url() -> str:
    """Get the runtime (app user) database URL."""
    return get_database_settings().app_url


DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    # More conservative pool settings
    pool_size=10,  # Adjust based on concurrent load
    max_overflow=20,  # Total max: 20 connections per instance
    pool_pre_ping=True,  # Keep this
    pool_recycle=3600,  # 1 hour instead of 30 min
    pool_timeout=10,  # Slightly shorter timeout
    # Optimized connection args
    connect_args={
        "connect_timeout": 10,  # Allow a bit more time
        "application_name": "rhesis-backend",
        "keepalives_idle": "300",  # More aggressive keepalive
        "keepalives_interval": "10",  # Check more frequently
        "keepalives_count": "3",
        # Additional recommended settings
        "tcp_user_timeout": "30000",  # 30 second TCP timeout
    },
)


# Connection event handlers removed - session variables are now set efficiently
# in the dependency injection system when needed, avoiding multiple DB round trips

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,  # Do not expire objects after commit
)
Base = declarative_base()

# Use context vars to ensure isolation between requests
_current_tenant_organization_id: ContextVar[Optional[str]] = ContextVar(
    "organization_id", default=None
)
_current_tenant_user_id: ContextVar[Optional[str]] = ContextVar("user_id", default=None)

# Context variable to control soft delete filtering
_soft_delete_disabled: ContextVar[bool] = ContextVar("soft_delete_disabled", default=False)


def clear_tenant_context():
    """Clear the tenant context variables"""
    try:
        token1 = _current_tenant_organization_id.set(None)
        token2 = _current_tenant_user_id.set(None)
        # Return tokens for proper context var management
        return token1, token2
    except Exception as e:
        logger.debug(f"Error clearing tenant context: {e}")
        return None, None


def reset_session_context(db: Session):
    """
    Reset PostgreSQL session variables for row-level security.

    This function safely resets session variables to empty strings rather than NULL
    to prevent "unrecognized configuration parameter" errors. It's now more robust
    and handles cases where variables might not have been initialized.
    """
    try:
        # Clear stored vars first so after_begin does not re-apply them after reset.
        db.info.pop(_TENANT_VARS_KEY, None)

        # Reset to empty strings (not NULL) to prevent errors
        # Empty strings are safer than NULL for current_setting() calls
        _set_session_variables(db)

        # Also clear context vars for backward compatibility
        clear_tenant_context()

        logger.debug("Successfully reset session variables to empty strings")

    except Exception as e:
        logger.debug(f"Error resetting RLS session context: {e}")


def set_session_variables(db: Session, organization_id: str, user_id: str, project_id: str = ""):
    """Set PostgreSQL RLS GUCs without activating the ORM auto-filter/auto-stamp listeners.

    This is the low-level primitive used by ``temporary_project_scope``. Prefer that
    context manager for temporary scope windows. Use this function directly only when
    you need explicit control over the before/after GUC values without a context manager.

    Does NOT write to ``db.info['_scope']``, so the ORM listeners stay dormant and
    there is no scope leakage into subsequent queries after you are done.
    """
    try:
        _set_session_variables(db, organization_id, user_id, project_id)
        logger.debug(
            f"Manually set session variables: org={organization_id}, user={user_id}, "
            f"project={project_id}"
        )

    except Exception as e:
        logger.warning(f"Failed to manually set session variables: {e}")
        raise


@contextmanager
def temporary_project_scope(
    db: Session, organization_id: str, user_id: str, project_id: str
) -> Generator[None, None, None]:
    """Temporarily shift the session to a specific project scope, then restore it.

    Use this when a single operation inside an ongoing request needs project-level RLS
    GUCs (e.g. inserting an endpoint whose ``project_id`` must match
    ``app.current_project``) but the surrounding request runs at org-level with no
    active project.

    Sets only the RLS GUCs via ``set_session_variables`` — does NOT write to
    ``db.info['_scope']``, so the ORM auto-filter/auto-stamp listeners stay dormant
    and there is no scope leakage into subsequent queries after the block exits.

    Use ``bind_scope_to_session`` instead when you own a long-lived session (Celery
    task, WebSocket handler) and want both RLS and ORM listeners active for the
    session's full lifetime.

    Example::

        with temporary_project_scope(db, organization_id, user_id, str(project.id)):
            db.add(Endpoint(...))
            db.flush()
    """
    set_session_variables(db, organization_id, user_id, project_id)
    try:
        yield
    finally:
        set_session_variables(db, organization_id, user_id, "")


@contextmanager
def without_soft_delete_filter():
    """
    Context manager to temporarily disable soft delete filtering.

    This allows queries to include soft-deleted records within the context block.
    Useful for admin operations, data recovery, and debugging.

    Usage:
        with without_soft_delete_filter():
            # Queries here will include soft-deleted records
            all_users = db.query(User).all()
            deleted_tests = db.query(Test).filter(Test.deleted_at.isnot(None)).all()

    Example:
        # Normal query (excludes deleted)
        active_users = db.query(User).all()

        # With context manager (includes deleted)
        with without_soft_delete_filter():
            all_users = db.query(User).all()
    """
    token = _soft_delete_disabled.set(True)
    try:
        yield
    finally:
        _soft_delete_disabled.reset(token)


def is_soft_delete_disabled() -> bool:
    """
    Check if soft delete filtering is currently disabled.

    This function is used by the event listener and query builder to determine
    whether to apply soft delete filters.

    Returns:
        True if soft delete filtering is disabled, False otherwise
    """
    return _soft_delete_disabled.get(False)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Get a database session with transparent transaction management.

    For operations requiring tenant context, use get_db_with_tenant_variables().
    This function provides a basic session for operations like user lookup,
    token validation, and other non-tenant-specific queries.
    """
    db = SessionLocal()
    try:
        yield db
        if db.in_transaction():
            db.commit()
    except Exception:
        if db.in_transaction():
            db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_with_tenant_variables(
    organization_id: str = "", user_id: str = "", project_id: str = ""
) -> Generator[Session, None, None]:
    """
    Get a database session with tenant context automatically set.

    This is the centralized function used by both FastAPI dependencies and task system.
    It sets PostgreSQL RLS session variables AND stores a RequestScope on
    ``session.info`` so the auto-filter / auto-stamp listeners activate for the
    duration of the session.  The ContextVar is NOT bound here — Session.info is
    the authoritative source for all DB-bound work (FastAPI requests and Celery
    tasks).  Only explicit ``bind_scope()`` callers (scripts, tests) use the
    ContextVar path.

    Args:
        organization_id: Organization ID for session variables and scope
        user_id: User ID for session variables and scope
        project_id: Project ID for session variables and scope (optional)

    Yields:
        Session: Database session with tenant context set and RequestScope in
        ``session.info``
    """
    from rhesis.backend.app.scope import RequestScope

    scope = RequestScope(
        organization_id=organization_id or None,
        user_id=user_id or None,
        project_id=project_id or None,
    )

    with get_db() as db:
        # Store the scope on Session.info as the SINGLE per-session source of
        # truth. The SQLAlchemy event listeners (auto_filter, auto_stamp) read it
        # via query.session.info / session.info regardless of whether the caller
        # is an async or sync route handler, and the after_begin listener
        # re-applies the RLS GUCs from this same object — no parallel _tenant_vars
        # dict is written on this path. The ContextVar (bind_scope) is only for
        # code that needs ambient scope without a DB session (scripts/tests).
        db.info[_SCOPE_KEY] = scope
        _apply_scope_variables(db, scope)
        try:
            yield db
            # Commit deferred writes while the tenant GUCs are still valid. ORM
            # changes assigned but not flushed by the caller (e.g. setting
            # ``test_set.attributes`` last in bulk_create_test_set) are otherwise
            # flushed by get_db()'s trailing commit, which runs AFTER the finally
            # block below has blanked the GUCs via reset_session_context(). That
            # ordering flushed the UPDATE under an empty app.current_organization,
            # and the RLS tenant_isolation policy's ''::uuid cast rejected it.
            # Committing here guarantees pending work lands under valid scope.
            if db.in_transaction():
                db.commit()
        finally:
            # Remove scope so it cannot be observed after the session is returned to
            # the pool / closed.
            db.info.pop(_SCOPE_KEY, None)
            # Belt-and-suspenders: reset RLS vars before connection returns to pool.
            # The GUCs are set with is_local=true (transaction-scoped) so this is
            # only needed when the connection is reused across transactions. Safe to
            # run here because any deferred writes were already committed above.
            try:
                reset_session_context(db)
            except Exception:
                pass  # best-effort; do not mask the original exception


# For tenant-aware operations, use get_db_with_tenant_variables()
# For basic operations, use get_db() and pass tenant context to CRUD functions
