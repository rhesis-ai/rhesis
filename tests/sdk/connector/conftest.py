"""Pytest configuration for connector tests."""

import pytest

from tests.sdk.conftest import RHESIS_API_KEY


@pytest.fixture(autouse=True)
def set_connector_env_vars(monkeypatch):
    monkeypatch.setenv("RHESIS_API_KEY", RHESIS_API_KEY)
    monkeypatch.setenv("RHESIS_PROJECT_ID", "test-project-id")
    monkeypatch.setenv("RHESIS_ENVIRONMENT", "test")
