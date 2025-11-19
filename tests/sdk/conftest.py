"""Shared pytest configuration for SDK tests."""

import pytest


# RHESIS_API_KEY should not be changed as it is used in integration tests auth
@pytest.fixture(autouse=True)
def set_api_keys(monkeypatch):
    """Automatically set API keys for all SDK tests."""
    monkeypatch.setenv("RHESIS_API_KEY", "rh-test-token")
    monkeypatch.setenv("GEMINI_API_KEY", "test_api_key")
