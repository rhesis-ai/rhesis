"""
🔢 Identifier Utility Fixtures

Fixtures for generating test identifiers, UUIDs, and ID-related test data.
"""

import uuid

import pytest


@pytest.fixture
def invalid_uuid() -> str:
    """❌ Generate a random UUID for testing not-found scenarios"""
    return str(uuid.uuid4())


@pytest.fixture
def malformed_uuid() -> str:
    """💥 Generate an invalid UUID string for testing validation"""
    return "not-a-valid-uuid-format"
