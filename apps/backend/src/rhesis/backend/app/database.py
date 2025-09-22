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

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    # More conservative pool settings
    pool_size=10,              # Adjust based on concurrent load
    max_overflow=20,           # Total max: 30 connections per instance
    pool_pre_ping=True,        # Keep this
    pool_recycle=3600,         # 1 hour instead of 30 min
    pool_timeout=10,           # Slightly shorter timeout
    # Optimized connection args
    connect_args={
        "connect_timeout": 10,          # Allow a bit more time
        "application_name": "rhesis-backend",
        "keepalives_idle": "300",       # More aggressive keepalive
        "keepalives_interval": "10",    # Check more frequently
        "keepalives_count": "3",
        # Additional recommended settings
        "tcp_user_timeout": "30000",    # 30 second TCP timeout
    }
)

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


# Removed legacy get_current_user_id and get_current_organization_id functions
# These are no longer needed - use direct parameter passing to CRUD functions


# Legacy set_tenant functions removed - use direct parameter passing instead

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
        # Use set_config with NULL to clear session variables
        db.execute(text("SELECT set_config('app.current_organization', NULL, false)"))
        db.execute(text("SELECT set_config('app.current_user', NULL, false)"))
        # Also clear context vars
        clear_tenant_context()
    except Exception as e:
        logger.debug(f"Error resetting RLS session context: {e}")




def init_db():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Get a simple database session without tenant context.
    
    For operations requiring tenant context, use get_db() and pass organization_id/user_id to CRUD functions.
    This function provides a basic session for operations like user lookup,
    token validation, and other non-tenant-specific queries.
    
    Uses automatic transaction management for consistency.
    """
    db = SessionLocal()
    try:
        # Use automatic transaction management for consistency
        with db.begin():
            # Start with a clean session
            db.expire_all()

            yield db
            # Transaction commits automatically if no exception occurred
    except Exception:
        # Transaction rolls back automatically via db.begin() context manager
        raise
    finally:
        # Close the session
        db.close()


# get_org_aware_db function has been completely removed
# Use get_db() and pass organization_id/user_id directly to CRUD functions
# Example: crud.create_item(db, model, data, organization_id=organization_id, user_id=user_id)


# Removed legacy get_current_*_cached functions
# These are no longer needed - use direct parameter passing to CRUD functions
