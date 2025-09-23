"""
Security Testing Configuration

This module provides shared fixtures and configuration for security tests.
"""

import pytest
from sqlalchemy.orm import Session


@pytest.fixture
def setup_test_database():
    """
    Setup fixture that ensures the test database is properly initialized.
    This fixture is used by db_session to trigger database cleanup.
    """
    # This fixture just ensures the database is ready
    # The actual cleanup is handled by the main conftest.py
    yield


@pytest.fixture
def db_session(setup_test_database):
    """
    Database session for security tests that triggers cleanup but avoids auth dependencies.
    
    This fixture provides a clean database session for each security test,
    ensuring proper isolation and cleanup without relying on authentication state.
    """
    from tests.backend.conftest import TestingSessionLocal
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
