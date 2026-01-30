"""
Database configuration tests.

This module tests database configuration and isolation to ensure
test databases are properly configured and isolated from production.
"""

import os

import pytest
from sqlalchemy import text

from rhesis.backend.app.database import SQLALCHEMY_DATABASE_URL, get_database_url
from tests.backend.db.utils import (
    DatabaseTestDataManager as TestDataManager,
)
from tests.backend.db.utils import (
    assert_test_database_used,
    get_test_database_stats,
    setup_test_environment,
)


@pytest.mark.unit
def test_database_url_configuration():
    """🗄️ Test that database URL configuration respects test mode."""
    # Verify we're in test mode
    assert os.getenv("SQLALCHEMY_DB_MODE") == "test"

    # Verify the database URL function works correctly
    url = get_database_url()
    expected_test_url = os.getenv("SQLALCHEMY_DATABASE_TEST_URL")
    assert expected_test_url, "SQLALCHEMY_DATABASE_TEST_URL must be set for testing"
    assert url == expected_test_url

    # Verify the global SQLALCHEMY_DATABASE_URL is using test database
    assert SQLALCHEMY_DATABASE_URL == expected_test_url


@pytest.mark.integration
@pytest.mark.database
def test_database_connection(test_db):
    """🔗 Test that database connection works with test database."""
    # Verify we can execute a simple query
    result = test_db.execute(text("SELECT 1 as test_value")).fetchone()
    assert result[0] == 1

    # Test transaction isolation
    test_db.execute(text("CREATE TEMPORARY TABLE IF NOT EXISTS test_isolation (id INTEGER)"))
    test_db.execute(text("INSERT INTO test_isolation (id) VALUES (1)"))

    result = test_db.execute(text("SELECT COUNT(*) FROM test_isolation")).fetchone()
    assert result[0] == 1


@pytest.mark.integration
@pytest.mark.database
def test_test_data_manager(test_db):
    """👥 Test the TestDataManager utility."""
    manager = TestDataManager(test_db)

    # Test basic database connection and session management
    assert manager.session is not None
    assert manager._created_objects == []

    # Test simple query to verify database connectivity
    result = test_db.execute(text("SELECT 1 as test_value")).fetchone()
    assert result[0] == 1

    # Note: User/Organization creation tests would require schema migration
    # This test focuses on the infrastructure rather than specific models


@pytest.mark.unit
def test_environment_context_manager():
    """🌍 Test the test_environment context manager."""
    # Test with custom environment variables
    with setup_test_environment(env_vars={"TEST_VAR": "test_value"}):
        assert os.getenv("TEST_VAR") == "test_value"
        assert os.getenv("SQLALCHEMY_DB_MODE") == "test"

    # Verify cleanup
    assert os.getenv("TEST_VAR") is None


@pytest.mark.unit
def test_different_database_urls():
    """🔄 Test database URL switching with different PostgreSQL configurations."""
    # Test PostgreSQL configuration
    postgres_url = "postgresql://test_user:test_pass@localhost:5432/test_db"
    with setup_test_environment(test_db_url=postgres_url):
        assert os.getenv("SQLALCHEMY_DATABASE_TEST_URL") == postgres_url

    # Test Cloud SQL Unix socket configuration
    cloudsql_url = "postgresql://user:pass@/test_db?host=/tmp/cloudsql/project:region:instance"
    with setup_test_environment(test_db_url=cloudsql_url):
        assert os.getenv("SQLALCHEMY_DATABASE_TEST_URL") == cloudsql_url


@pytest.mark.integration
@pytest.mark.database
def test_fastapi_client_database_integration(client):
    """🌐 Test that FastAPI client uses test database."""
    # Make a request that would interact with the database
    response = client.get("/")  # Assuming this is a valid endpoint

    # The response itself doesn't matter as much as ensuring
    # the client is using the test database without errors
    assert response.status_code in [200, 404, 422]  # Any reasonable HTTP status

    # Verify we're still in test mode after the request
    assert_test_database_used()


@pytest.mark.unit
def test_database_stats():
    """📊 Test database statistics reporting."""
    stats = get_test_database_stats()

    required_keys = [
        "test_mode",
        "test_db_url",
        "actual_db_url",
        "is_postgres",
        "is_cloud_sql",
        "isolation_verified",
    ]

    for key in required_keys:
        assert key in stats, f"Missing key: {key}"

    assert stats["test_mode"] == "test"
    assert stats["isolation_verified"] is True


if __name__ == "__main__":
    # Run this file directly to check database configuration
    print("🗄️ Database Configuration Check")
    print("=" * 50)

    stats = get_test_database_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")

    try:
        assert_test_database_used()
        print("\n✅ Test database configuration is correct!")
    except AssertionError as e:
        print(f"\n❌ Test database configuration error: {e}")
