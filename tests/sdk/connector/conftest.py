"""Pytest configuration for connector tests."""

import pytest


@pytest.fixture(autouse=True)
def set_connector_env_vars(monkeypatch):
    """Set environment variables for connector tests."""
    monkeypatch.setenv("RHESIS_API_KEY", "test-api-key")
    monkeypatch.setenv("RHESIS_PROJECT_ID", "test-project-id")
    monkeypatch.setenv("RHESIS_ENVIRONMENT", "test")
