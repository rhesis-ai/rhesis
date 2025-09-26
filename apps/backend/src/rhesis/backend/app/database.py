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

# Cache for session variables to avoid unnecessary re-setting
# Key format: (connection_id, organization_id, user_id) for security
_session_variable_cache = {}


def _set_session_variables_raw(cursor, organization_id: str = '', user_id: str = ''):
    """
    Set PostgreSQL session variables using a raw database cursor.
    
    This is a low-level utility function used by connection event handlers
    and other functions that need to set session variables.
    
    Args:
        cursor: Database cursor (psycopg2 or similar)
        organization_id: Organization ID (defaults to empty string)
        user_id: User ID (defaults to empty string)
    """
    cursor.execute("SELECT set_config('app.current_organization', %s, false)", (organization_id,))
    cursor.execute("SELECT set_config('app.current_user', %s, false)", (user_id,))


def _set_session_variables(db: Session, organization_id: str = '', user_id: str = ''):
    """
    Set PostgreSQL session variables using SQLAlchemy session.
    
    This function handles cases where the variables might not exist yet by
    gracefully creating them. It's optimized to minimize database round trips.
    Uses caching to avoid re-setting variables if they're already correct.
    
    Args:
        db: SQLAlchemy session
        organization_id: Organization ID (defaults to empty string)
        user_id: User ID (defaults to empty string)
    """
    logger.info(f"🔧 [DB] Setting session variables: org={organization_id[:8]}..., user={user_id[:8]}...")
    
    # OPTIMIZATION: Check cache to avoid unnecessary DB operations
    # SECURITY: Include tenant context in cache key to prevent cross-user contamination
    connection_id = id(db.connection())
    cache_key = (connection_id, organization_id, user_id)
    
    if cache_key in _session_variable_cache:
        logger.info("⚡ [DB] Session variables already set for this user/org - SKIPPING (cached)")
        return
    
    try:
        # OPTIMIZATION: Set both variables in a single SQL statement
        logger.info("📝 [DB] Executing BATCHED set_config for both variables")
        db.execute(
            text("""
                SELECT 
                    set_config('app.current_organization', :org_id, false),
                    set_config('app.current_user', :user_id, false)
            """), 
            {"org_id": organization_id, "user_id": user_id}
        )
        
        # Cache the values for this specific connection + user/org combination
        _session_variable_cache[cache_key] = True
        logger.info("✅ [DB] Session variables set successfully (BATCHED + CACHED)")
        
    except Exception as e:
        # If variables don't exist, this will create them automatically
        # PostgreSQL set_config creates the variable if it doesn't exist
        logger.warning(f"⚠️ [DB] Session variables set with potential creation: {e}")
        # Re-raise only if it's a serious error, not just "variable doesn't exist"
        if "unrecognized configuration parameter" not in str(e).lower():
            raise


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


# Connection event handlers removed - session variables are now set efficiently
# in the dependency injection system when needed, avoiding multiple DB round trips

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
    """
    Reset PostgreSQL session variables for row-level security.
    
    This function safely resets session variables to empty strings rather than NULL
    to prevent "unrecognized configuration parameter" errors. It's now more robust
    and handles cases where variables might not have been initialized.
    """
    try:
        # Reset to empty strings (not NULL) to prevent errors
        # Empty strings are safer than NULL for current_setting() calls
        _set_session_variables(db)
        
        # Also clear context vars for backward compatibility
        clear_tenant_context()
        
        logger.debug("Successfully reset session variables to empty strings")
        
    except Exception as e:
        logger.debug(f"Error resetting RLS session context: {e}")


def set_session_variables(db: Session, organization_id: str, user_id: str):
    """
    Explicitly set PostgreSQL session variables for RLS policies.
    
    This is a utility function that can be used when you need to manually
    set session variables outside of the dependency injection system.
    
    Args:
        db: Database session
        organization_id: Organization UUID as string
        user_id: User UUID as string
    """
    try:
        _set_session_variables(db, organization_id, user_id)
        logger.debug(f"Manually set session variables: org={organization_id}, user={user_id}")
        
    except Exception as e:
        logger.warning(f"Failed to manually set session variables: {e}")
        raise




def init_db():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Get a simple database session with transparent transaction management.
    
    For operations requiring tenant context, use get_db() and pass organization_id/user_id to CRUD functions.
    This function provides a basic session for operations like user lookup,
    token validation, and other non-tenant-specific queries.
    
    Uses transparent transaction management - transactions are handled automatically
    by SQLAlchemy based on the session configuration (autocommit=False, autoflush=False).
    Clients don't need to explicitly manage transactions.
    """
    logger.info("🔌 [DB] Creating new database session")
    db = SessionLocal()
    try:
        yield db
        # Commit any pending transactions automatically
        if db.in_transaction():
            logger.info("💾 [DB] Committing transaction")
            db.commit()
        else:
            logger.info("✅ [DB] No transaction to commit")
    except Exception as e:
        # Rollback on exception
        if db.in_transaction():
            logger.error(f"🔄 [DB] Rolling back transaction due to error: {e}")
            db.rollback()
        raise
    finally:
        # Clean up session variable cache for this connection
        # SECURITY: Remove all cache entries for this connection to prevent leaks
        try:
            connection_id = id(db.connection()) if hasattr(db, 'connection') else None
            if connection_id:
                # Remove all cache entries for this connection (regardless of user/org)
                keys_to_remove = [key for key in _session_variable_cache.keys() 
                                if key[0] == connection_id]
                for key in keys_to_remove:
                    del _session_variable_cache[key]
                if keys_to_remove:
                    logger.info(f"🧹 [DB] Cleaned up {len(keys_to_remove)} session variable cache entries")
        except Exception as e:
            logger.debug(f"Cache cleanup error (non-critical): {e}")
        
        # Close the session
        logger.info("🔐 [DB] Closing database session")
        db.close()


# get_org_aware_db function has been completely removed
# Use get_db() and pass organization_id/user_id directly to CRUD functions
# Example: crud.create_item(db, model, data, organization_id=organization_id, user_id=user_id)


# Removed legacy get_current_*_cached functions
# These are no longer needed - use direct parameter passing to CRUD functions
