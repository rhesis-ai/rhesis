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


def _set_session_variables(
    db: Session, organization_id: str = "", user_id: str = "", project_id: str = ""
):
    """
    Set PostgreSQL session variables using SQLAlchemy session.

    Always executes the SET call — the cost of a single ``set_config``
    round-trip is negligible compared to any query that follows.

    Uses is_local=true (transaction-scoped). Variables survive within a
    transaction but are cleared by db.commit(). The Session.after_begin
    listener (_reapply_tenant_vars) re-applies them at the start of every
    new transaction so that mid-request commits do not break RLS.

    Args:
        db: SQLAlchemy session
        organization_id: Organization ID (defaults to empty string)
        user_id: User ID (defaults to empty string)
        project_id: Project ID (defaults to empty string)
    """
    vars = {"org_id": organization_id, "user_id": user_id, "project_id": project_id}
    # Persist in session.info so after_begin can re-apply after each commit.
    db.info[_TENANT_VARS_KEY] = vars
    try:
        db.execute(_SET_CONFIG_SQL, vars)
        logger.debug(
            f"Session variables set: org={organization_id}, user={user_id}, project={project_id}"
        )
    except Exception as e:
        logger.debug(f"Session variables set with potential creation: {e}")
        if "unrecognized configuration parameter" not in str(e).lower():
            raise


@event.listens_for(Session, "after_begin")
def _reapply_tenant_vars(session: Session, transaction, connection) -> None:
    """
    Re-apply RLS GUCs at the start of every new transaction.

    set_config(..., is_local=true) is transaction-scoped: values are cleared
    when a transaction ends (commit or rollback). This listener re-applies
    the stored tenant vars so that code that calls db.commit() mid-request
    (e.g. Celery tasks, nested CRUD helpers) continues to be RLS-filtered
    on subsequent queries within the same session.

    NOTE: This is intentionally NOT gated by RHESIS_DISABLE_SCOPE_LISTENER. That
    kill switch disables only the ORM-layer auto-filter/auto-stamp listeners; the
    RLS GUCs are the database-level security backstop and must keep being applied
    even when the ORM listeners are turned off. Disabling them would weaken, not
    relax, tenant isolation.
    """
    vars = session.info.get(_TENANT_VARS_KEY)
    if not vars:
        return
    try:
        connection.execute(_SET_CONFIG_SQL, vars)
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
    """
    Explicitly set PostgreSQL session variables for RLS policies.

    Prefer get_db_with_tenant_variables() which also stores the RequestScope on
    Session.info for automatic auto-filter / auto-stamp. Use this function only when
    you already have a session and need to set RLS variables without creating a new one.

    NOTE: This function sets RLS variables but does NOT store a RequestScope on
    Session.info. If you need the auto-filter/auto-stamp listeners to activate, set
    db.info["_scope"] = RequestScope(...) yourself (or use get_db_with_tenant_variables).

    Args:
        db: Database session
        organization_id: Organization UUID as string
        user_id: User UUID as string
        project_id: Project UUID as string (optional)
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
        _set_session_variables(db, organization_id, user_id, project_id)

        # Store scope on Session.info so SQLAlchemy event listeners
        # (auto_filter, auto_stamp) can read it via query.session.info / session.info
        # regardless of whether the caller is an async or sync route handler. This is
        # the authoritative source for all DB-bound work (FastAPI requests AND Celery
        # tasks, which both go through this function). The ContextVar (bind_scope) is
        # only for code that needs ambient scope without a DB session (scripts/tests).
        db.info[_SCOPE_KEY] = scope
        try:
            yield db
        finally:
            # Remove scope so it cannot be observed after the session is returned to
            # the pool / closed.
            db.info.pop(_SCOPE_KEY, None)
            # Belt-and-suspenders: reset RLS vars before connection returns to pool.
            # _set_session_variables uses is_local=true (transaction-scoped) so this
            # is only needed when the connection is reused across transactions.
            try:
                reset_session_context(db)
            except Exception:
                pass  # best-effort; do not mask the original exception


# For tenant-aware operations, use get_db_with_tenant_variables()
# For basic operations, use get_db() and pass tenant context to CRUD functions
