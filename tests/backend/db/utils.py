"""
Database testing utilities.

This module provides utilities for database testing including
environment setup, test data management, and database verification.

Note: This module name does not follow the test_* pattern to prevent
pytest from attempting to collect the utility classes as tests.
"""

import os
import tempfile
from typing import Generator, Optional
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from rhesis.backend.app.database import Base


@contextmanager
def setup_test_environment(
    test_db_url: Optional[str] = None, env_vars: Optional[dict] = None
) -> Generator[None, None, None]:
    """
    Context manager for setting up a clean test environment.

    Args:
        test_db_url: Optional custom test database URL
        env_vars: Optional dictionary of environment variables to set

    Usage:
        with setup_test_environment(env_vars={"API_KEY": "test-key"}):
            # Your test code here
            pass
    """
    # Store original environment variables
    original_env = {}

    try:
        # Set SQLALCHEMY_DB_MODE to test
        original_env["SQLALCHEMY_DB_MODE"] = os.environ.get("SQLALCHEMY_DB_MODE")
        os.environ["SQLALCHEMY_DB_MODE"] = "test"

        # Set test database URL if provided
        if test_db_url:
            original_env["SQLALCHEMY_DATABASE_TEST_URL"] = os.environ.get(
                "SQLALCHEMY_DATABASE_TEST_URL"
            )
            os.environ["SQLALCHEMY_DATABASE_TEST_URL"] = test_db_url

        # Set additional environment variables if provided
        if env_vars:
            for key, value in env_vars.items():
                original_env[key] = os.environ.get(key)
                os.environ[key] = value

        yield

    finally:
        # Restore original environment variables
        for key, original_value in original_env.items():
            if original_value is None:
                # Remove the key if it wasn't set originally
                os.environ.pop(key, None)
            else:
                # Restore the original value
                os.environ[key] = original_value


def create_temp_postgres_db() -> str:
    """
    Create a temporary PostgreSQL database URL for testing.
    Note: This assumes you have PostgreSQL running locally.

    Returns:
        str: PostgreSQL URL for a temporary test database
    """
    import uuid

    temp_db_name = f"temp_test_{uuid.uuid4().hex[:8]}"
    return f"postgresql://localhost:5432/{temp_db_name}"


def create_test_session(test_db_url: str) -> Generator[Session, None, None]:
    """
    Create a test database session with automatic cleanup.

    Args:
        test_db_url: Database URL for testing

    Yields:
        Session: SQLAlchemy session for testing
    """
    engine = create_engine(test_db_url, echo=False)
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def verify_test_database_isolation() -> bool:
    """
    Verify that test database is properly isolated from production database.

    Returns:
        bool: True if isolation is working correctly
    """
    # Check that SQLALCHEMY_DB_MODE is set to test
    if os.getenv("SQLALCHEMY_DB_MODE") != "test":
        return False

    # Check that we're using the test database URL
    test_url = os.getenv("SQLALCHEMY_DATABASE_TEST_URL")
    if not test_url:
        return False

    # Ensure we're not accidentally using the production database
    prod_url = os.getenv("SQLALCHEMY_DATABASE_URL")
    if test_url == prod_url and prod_url and "test" not in prod_url.lower():
        return False

    # Ensure test URL contains 'test' (PostgreSQL requirement)
    if "test" not in test_url.lower():
        return False

    return True


class DatabaseTestDataManager:
    """
    Helper class for managing test data creation and cleanup.
    """

    def __init__(self, session: Session):
        self.session = session
        self._created_objects = []

    def create_user(self, **kwargs):
        """Create a test user with default or custom attributes."""
        from rhesis.backend.app.models import User

        defaults = {
            "email": "test@example.com",
            "name": "Test User",  # Changed from display_name to name
        }
        defaults.update(kwargs)

        user = User(**defaults)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)

        self._created_objects.append(user)
        return user

    def create_organization(self, **kwargs):
        """Create a test organization with default or custom attributes."""
        from rhesis.backend.app.models import Organization

        defaults = {
            "name": "Test Organization",
            "description": "Test organization for unit tests",
        }
        defaults.update(kwargs)

        organization = Organization(**defaults)
        self.session.add(organization)
        self.session.commit()
        self.session.refresh(organization)

        self._created_objects.append(organization)
        return organization

    def cleanup(self):
        """Clean up all created test objects."""
        for obj in reversed(self._created_objects):
            self.session.delete(obj)
        self.session.commit()
        self._created_objects.clear()


def assert_test_database_used():
    """
    Assert that we're using the test database.
    Raises AssertionError if not using test database.
    """
    from rhesis.backend.app.database import SQLALCHEMY_DATABASE_URL

    assert os.getenv("SQLALCHEMY_DB_MODE") == "test", "SQLALCHEMY_DB_MODE should be 'test'"

    test_url = os.getenv("SQLALCHEMY_DATABASE_TEST_URL")
    assert test_url, "SQLALCHEMY_DATABASE_TEST_URL must be set"

    assert SQLALCHEMY_DATABASE_URL == test_url, (
        f"Expected to use test database {test_url}, but using {SQLALCHEMY_DATABASE_URL}"
    )


def get_test_database_stats() -> dict:
    """
    Get statistics about the current test database configuration.

    Returns:
        dict: Database configuration statistics
    """
    from rhesis.backend.app.database import SQLALCHEMY_DATABASE_URL

    return {
        "test_mode": os.getenv("SQLALCHEMY_DB_MODE"),
        "test_db_url": os.getenv("SQLALCHEMY_DATABASE_TEST_URL"),
        "actual_db_url": SQLALCHEMY_DATABASE_URL,
        "is_postgres": "postgresql" in SQLALCHEMY_DATABASE_URL.lower(),
        "is_cloud_sql": "/cloudsql/" in SQLALCHEMY_DATABASE_URL
        or "/tmp/cloudsql/" in SQLALCHEMY_DATABASE_URL,
        "isolation_verified": verify_test_database_isolation(),
    }
