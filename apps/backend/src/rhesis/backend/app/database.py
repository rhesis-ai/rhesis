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


def get_database_url() -> str:
    """Get the appropriate database URL based on the current mode."""
    # In test mode, prioritize SQLALCHEMY_DATABASE_TEST_URL
    if os.getenv("SQLALCHEMY_DB_MODE") == "test":
        test_url = os.getenv("SQLALCHEMY_DATABASE_TEST_URL")
        if test_url:
            return test_url

    # For production/development, use SQLALCHEMY_DATABASE_URL if available
    prod_url = os.getenv("SQLALCHEMY_DATABASE_URL")
    if prod_url:
        return prod_url

    # Fallback: construct URL from individual components
    return _construct_database_url(is_test=os.getenv("SQLALCHEMY_DB_MODE") == "test")


def _construct_database_url(is_test: bool = False) -> str:
    """Construct database URL from environment variables."""
    user = os.getenv("SQLALCHEMY_DB_USER", "")
    password = os.getenv("SQLALCHEMY_DB_PASS", "")
    host = os.getenv("SQLALCHEMY_DB_HOST", "")
    db_name = os.getenv("SQLALCHEMY_DB_NAME", "")

    # Add -test suffix for test databases
    if is_test:
        db_name += "-test"

    # Handle Cloud SQL Unix socket connections
    if host.startswith(("/cloudsql", "/tmp/cloudsql")):
        return f"postgresql://{user}:{password}@/{db_name}?host={host}"

    # Default to localhost TCP connection
    return f"postgresql://{user}:{password}@localhost:5432/{db_name}"


SQLALCHEMY_DATABASE_URL = get_database_url()

# Create engine with proper configuration
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,  # Expire objects after commit
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
        # Return None if result is None, empty string, or can't be converted to UUID
        if not result or result == "" or (isinstance(result, str) and result.strip() == ""):
            return None
        # Validate that result is a valid UUID format before converting
        try:
            return UUID(result)
        except (ValueError, TypeError):
            logger.debug(f"Invalid UUID format for user ID: {result}")
            return None
    except Exception as e:
        logger.debug(f"Error getting current user ID: {e}")
        return None


def get_current_organization_id(session: Session) -> Optional[UUID]:
    """Get the current organization ID from the database session."""
    try:
        result = session.execute(text('SHOW "app.current_organization";')).scalar()
        logger.debug(
            f"get_current_organization_id - Raw result from DB: '{result}', type: {type(result)}"
        )
        # Return None if result is None, empty string, or can't be converted to UUID
        if not result or result == "" or (isinstance(result, str) and result.strip() == ""):
            logger.debug(
                f"get_current_organization_id - Returning None for empty/None result: '{result}'"
            )
            return None
        # Validate that result is a valid UUID format before converting
        try:
            uuid_result = UUID(result)
            logger.debug(f"get_current_organization_id - Returning valid UUID: {uuid_result}")
            return uuid_result
        except (ValueError, TypeError):
            logger.debug(
                f"get_current_organization_id - Invalid UUID format for organization ID: {result}"
            )
            return None
    except Exception as e:
        logger.debug(f"get_current_organization_id - Error getting current organization ID: {e}")
        return None


def _execute_set_tenant(
    connection, organization_id: Optional[str] = None, user_id: Optional[str] = None
):
    """Helper function to execute SET commands for tenant context"""
    try:
        # Only set if organization_id is not None, not empty, and is a valid UUID format
        if organization_id and organization_id.strip() and organization_id != "":
            # Validate UUID format before setting
            try:
                UUID(organization_id)  # Validate it's a proper UUID
                # logger.debug(f"Setting app.current_organization to: {organization_id}")
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
            except (ValueError, TypeError) as uuid_error:
                logger.debug(
                    f"Invalid UUID format for organization_id: {organization_id}, error: {uuid_error}"
                )
        else:
            pass
            # logger.debug("Not setting app.current_organization (empty or None)")

        # Only set if user_id is not None, not empty, and is a valid UUID format
        if user_id and user_id.strip() and user_id != "":
            # Validate UUID format before setting
            try:
                UUID(user_id)  # Validate it's a proper UUID
                # logger.debug(f"Setting app.current_user to: {user_id}")
                if hasattr(connection, "execute"):  # SQLAlchemy session
                    connection.execute(
                        text("SELECT set_config('app.current_user', :user_id, false)"),
                        {"user_id": str(user_id)},
                    )
                else:  # Raw database connection
                    cursor = connection.cursor()
                    cursor.execute(
                        "SELECT set_config('app.current_user', %s, false)", (str(user_id),)
                    )
                    cursor.close()
            except (ValueError, TypeError) as uuid_error:
                logger.debug(f"Invalid UUID format for user_id: {user_id}, error: {uuid_error}")
        else:
            pass
            # logger.debug("Not setting app.current_user (empty or None)")
    except Exception as e:
        logger.error(f"Error setting tenant context: {e}")
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
