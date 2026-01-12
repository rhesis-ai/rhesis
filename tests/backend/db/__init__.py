"""
Database testing utilities and configuration.

This module provides all database-related testing functionality including
configuration verification, test data management, and database utilities.
"""

from .utils import (
    DatabaseTestDataManager,
    assert_test_database_used,
    create_temp_postgres_db,
    create_test_session,
    get_test_database_stats,
    setup_test_environment,
    verify_test_database_isolation,
)

# Provide backward compatibility alias
TestDataManager = DatabaseTestDataManager

__all__ = [
    "setup_test_environment",
    "create_temp_postgres_db",
    "create_test_session",
    "verify_test_database_isolation",
    "TestDataManager",
    "DatabaseTestDataManager",
    "assert_test_database_used",
    "get_test_database_stats",
]
