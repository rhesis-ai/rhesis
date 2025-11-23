"""
Database testing utilities and configuration.

This module provides all database-related testing functionality including
configuration verification, test data management, and database utilities.
"""

from .utils import (
    setup_test_environment,
    create_temp_postgres_db,
    create_test_session,
    verify_test_database_isolation,
    DatabaseTestDataManager,
    assert_test_database_used,
    get_test_database_stats,
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
