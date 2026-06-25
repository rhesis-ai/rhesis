"""
Database testing utilities.

This module provides utilities for database testing including
environment setup, test data management, and database verification.

Note: This module name does not follow the test_* pattern to prevent
pytest from attempting to collect the utility classes as tests.
"""

import os
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from rhesis.backend.app.database import Base


_DB_COMPONENT_VARS = ("DB_DRIVER", "DB_HOST", "DB_PORT", "DB_NAME", "APP_DB_USER", "APP_DB_PASS")


@contextmanager
def setup_test_environment(
    test_db_url: Optional[str] = None, env_vars: Optional[dict] = None
) -> Generator[None, None, None]:
    """
    Context manager for setting up a clean test environment.

    Args:
        test_db_url: Optional database URL to parse into component env vars.
            The URL is parsed into DB_DRIVER, DB_HOST, DB_PORT, DB_NAME,
            APP_DB_USER, APP_DB_PASS so that DatabaseSettings can build the
            connection URL from components.
        env_vars: Optional dictionary of environment variables to set

    Usage:
        with setup_test_environment(env_vars={"API_KEY": "test-key"}):
            # Your test code here
            pass
    """
    from urllib.parse import urlparse, unquote

    original_env: dict[str, Optional[str]] = {}

    try:
        if test_db_url:
            parsed = urlparse(test_db_url)
            # Extract host and optional Unix-socket path (passed via ?host= query param)
            host = parsed.hostname or ""
            if not host and parsed.path and "?" in test_db_url:
                qs = test_db_url.split("?", 1)[1]
                for part in qs.split("&"):
                    if part.startswith("host="):
                        host = unquote(part[5:])
                        break
            component_vars = {
                "DB_DRIVER": parsed.scheme or "postgresql",
                "DB_HOST": host,
                "DB_PORT": str(parsed.port or 5432),
                "DB_NAME": (parsed.path or "").lstrip("/").split("?")[0],
                "APP_DB_USER": unquote(parsed.username or ""),
                "APP_DB_PASS": unquote(parsed.password or ""),
            }
            for key, value in component_vars.items():
                original_env[key] = os.environ.get(key)
                os.environ[key] = value

        if env_vars:
            for key, value in env_vars.items():
                original_env[key] = os.environ.get(key)
                os.environ[key] = value

        yield

    finally:
        for key, original_value in original_env.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
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
    db_name = os.getenv("DB_NAME", "")
    if not db_name:
        return False

    if "test" not in db_name.lower():
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
    from rhesis.backend.app.database import DATABASE_URL

    db_name = os.getenv("DB_NAME", "")
    assert db_name, "DB_NAME must be set"

    assert "test" in db_name.lower(), (
        f"Expected a test database (DB_NAME containing 'test'), but DB_NAME={db_name!r}"
    )
    assert DATABASE_URL, "DATABASE_URL must be non-empty"


def get_test_database_stats() -> dict:
    """
    Get statistics about the current test database configuration.

    Returns:
        dict: Database configuration statistics
    """
    from rhesis.backend.app.database import DATABASE_URL

    return {
        "configured_db_url": DATABASE_URL,
        "actual_db_url": DATABASE_URL,
        "is_postgres": "postgresql" in DATABASE_URL.lower(),
        "is_cloud_sql": "/cloudsql/" in DATABASE_URL or "/tmp/cloudsql/" in DATABASE_URL,
        "isolation_verified": verify_test_database_isolation(),
    }
