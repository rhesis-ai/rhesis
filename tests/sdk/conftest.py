"""Shared pytest configuration for SDK tests."""

import pytest


@pytest.fixture(autouse=True)
def set_api_keys(monkeypatch):
    """Automatically set API keys for all SDK tests."""
    monkeypatch.setenv("RHESIS_API_KEY", "test_api_key")
    monkeypatch.setenv("GEMINI_API_KEY", "test_api_key")
