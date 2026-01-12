"""
🗄️ Database Fixtures Module

This module contains all database-related fixtures for testing, including:
- Database engine and session configuration
- Database setup and teardown
- Test database session management

Extracted from conftest.py for better modularity and maintainability.
"""

from uuid import UUID

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from rhesis.backend.app.database import Base, get_database_url

# Test database configuration - use the same logic as main database file
# This ensures consistency between test and production database connections
SQLALCHEMY_DATABASE_TEST_URL = get_database_url()

# Create test engine with the same configuration as production
# but optimized for testing (smaller pool sizes)
test_engine = create_engine(
    SQLALCHEMY_DATABASE_TEST_URL,
    # Reduced pool settings for testing
    pool_size=5,  # Smaller than production (10)
    max_overflow=10,  # Smaller than production (20)
    pool_pre_ping=True,  # Same as production
    pool_recycle=3600,  # Same as production (1 hour)
    pool_timeout=10,  # Same as production
    # Same connection args as production
    connect_args={
        "connect_timeout": 10,  # Same as production
        "application_name": "rhesis-backend-test",  # Distinguish test connections
        "keepalives_idle": "300",  # Same as production
        "keepalives_interval": "10",  # Same as production
        "keepalives_count": "3",  # Same as production
        "tcp_user_timeout": "30000",  # Same as production
    },
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
    expire_on_commit=False,  # Same as production
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Set up the test database before any tests run."""
    # Create all tables in the test database
    Base.metadata.create_all(bind=test_engine)
    yield
    # Clean up after all tests are done
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def test_db(test_org_id, authenticated_user_id):
    """🗄️ Provide a database session for testing - allows service code to manage transactions."""
    from rhesis.backend.app.database import (
        _current_tenant_organization_id,
        _current_tenant_user_id,
        clear_tenant_context,
    )

    # Create session but let service code manage transactions (like production)
    db = TestingSessionLocal()
    try:
        # Set session variables (without SET LOCAL since no transaction context yet)
        if test_org_id:
            try:
                UUID(test_org_id)  # Validate UUID format
                db.execute(
                    text('SET "app.current_organization" = :org_id'), {"org_id": test_org_id}
                )
            except (ValueError, TypeError):
                raise ValueError(f"Invalid test_org_id: {test_org_id}")

        if authenticated_user_id:
            try:
                UUID(authenticated_user_id)  # Validate UUID format
                db.execute(
                    text('SET "app.current_user" = :user_id'), {"user_id": authenticated_user_id}
                )
            except (ValueError, TypeError):
                raise ValueError(f"Invalid authenticated_user_id: {authenticated_user_id}")

        # Store in context vars for any legacy code that might need it
        _current_tenant_organization_id.set(test_org_id)
        if authenticated_user_id:
            _current_tenant_user_id.set(authenticated_user_id)

        yield db
        # Let service code handle commit/rollback as it does in production

    finally:
        # Ensure any open transaction is rolled back
        try:
            if db.in_transaction():
                db.rollback()
        except Exception:
            pass

        # Clear context vars and close session
        clear_tenant_context()
        db.close()
