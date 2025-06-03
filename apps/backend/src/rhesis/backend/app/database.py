import os
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Generator, Optional
from uuid import UUID

from dotenv import load_dotenv
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from rhesis.backend.logging import logger

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL", "sqlite:///./test.db")

# Create engine with proper configuration
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=True,  # Expire objects after commit
)
Base = declarative_base()

# Use context vars to ensure isolation between requests
_current_tenant_organization_id: ContextVar[Optional[str]] = ContextVar(
    "organization_id", default=None
)
_current_tenant_user_id: ContextVar[Optional[str]] = ContextVar("user_id", default=None)


def get_current_user_id(session: Session) -> Optional[UUID]:
    """Get the current user ID from the database session."""
    try:
        result = session.execute(text('SHOW "app.current_user";')).scalar()
        return UUID(result) if result else None
    except Exception as e:
        logger.debug(f"Error getting current user ID: {e}")
        return None


def get_current_organization_id(session: Session) -> Optional[UUID]:
    """Get the current organization ID from the database session."""
    try:
        result = session.execute(text('SHOW "app.current_organization";')).scalar()
        return UUID(result) if result else None
    except Exception as e:
        logger.debug(f"Error getting current organization ID: {e}")
        return None


def _execute_set_tenant(
    connection, organization_id: Optional[str] = None, user_id: Optional[str] = None
):
    """Helper function to execute SET commands for tenant context"""
    try:
        if organization_id and organization_id.strip():  # Only set if organization_id is not empty
            if hasattr(connection, "execute"):  # SQLAlchemy session
                connection.execute(
                    text("SELECT set_config('app.current_organization', :org_id, false)"),
                    {"org_id": str(organization_id)},
                )
            else:  # Raw database connection
                cursor = connection.cursor()
                cursor.execute(
                    "SELECT set_config('app.current_organization', %s, false)",
                    (str(organization_id),),
                )
                cursor.close()

        if user_id and user_id.strip():  # Only set if user_id is not empty
            if hasattr(connection, "execute"):  # SQLAlchemy session
                connection.execute(
                    text("SELECT set_config('app.current_user', :user_id, false)"),
                    {"user_id": str(user_id)},
                )
            else:  # Raw database connection
                cursor = connection.cursor()
                cursor.execute("SELECT set_config('app.current_user', %s, false)", (str(user_id),))
                cursor.close()
    except Exception as e:
        logger.debug(f"Error setting tenant context: {e}")
        # Don't raise the exception - allow the operation to continue
        pass


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
    """Reset PostgreSQL session variables for row-level security."""
    try:
        # Use set_config with NULL instead of RESET to avoid issues with 
        # current_user reserved keyword
        db.execute(text("SELECT set_config('app.current_organization', NULL, false)"))
        db.execute(text("SELECT set_config('app.current_user', NULL, false)"))
        # Also clear context vars
        clear_tenant_context()
    except Exception as e:
        logger.debug(f"Error resetting RLS session context: {e}")


def set_tenant(
    session: Session, organization_id: Optional[str] = None, user_id: Optional[str] = None
):
    """Set PostgreSQL session variables for row-level security."""
    try:
        # Store in context vars
        if organization_id is not None:
            _current_tenant_organization_id.set(organization_id)
        if user_id is not None:
            _current_tenant_user_id.set(user_id)

        _execute_set_tenant(session, organization_id, user_id)
    except Exception as e:
        logger.debug(f"Error in set_tenant: {e}")


def _set_tenant_for_connection(dbapi_connection, connection_record):
    """Set tenant context for new connections"""
    try:
        org_id = _current_tenant_organization_id.get()
        user_id = _current_tenant_user_id.get()
        _execute_set_tenant(dbapi_connection, org_id, user_id)
    except Exception as e:
        logger.debug(f"Error in _set_tenant_for_connection: {e}")


# Register the event listener
event.listen(engine, "connect", _set_tenant_for_connection)


@contextmanager
def maintain_tenant_context(session: Session):
    """Maintain the tenant context across a transaction."""
    # Store current context
    try:
        prev_org_id = _current_tenant_organization_id.get()
        prev_user_id = _current_tenant_user_id.get()
    except Exception:
        prev_org_id = None
        prev_user_id = None

    # If transaction is active and dirty, commit it before starting a new one
    try:
        if session.in_transaction():
            if session.dirty or session.new or session.deleted:
                # Transaction has changes that might need handling
                pass

        # Set context before the operation
        set_tenant(session, prev_org_id, prev_user_id)
        yield
    except Exception:
        # Only rollback if there's an active transaction
        if session.in_transaction():
            session.rollback()
        raise
    finally:
        try:
            # Only commit if there are actual changes
            if session.in_transaction() and (session.dirty or session.new or session.deleted):
                session.commit()
            # Clean up tenant context
            _execute_set_tenant(session, None, None)
        except Exception as e:
            logger.debug(f"Error in maintain_tenant_context cleanup: {e}")
            if session.in_transaction():
                session.rollback()


def init_db():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Get a database session."""
    db = SessionLocal()
    try:
        # Start with a clean session
        db.expire_all()

        # Reset tenant context for this request
        org_token, user_token = clear_tenant_context()

        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        try:
            # Clean up any pending transaction
            if db.in_transaction():
                db.rollback()

            # Clear tenant context and session state
            _execute_set_tenant(db, None, None)
            clear_tenant_context()
            db.expire_all()

            # Close the session
            db.close()
        except Exception as e:
            logger.debug(f"Error during session cleanup: {e}")
            # Still try to close the session even if cleanup fails
            try:
                db.close()
            except Exception:
                pass
