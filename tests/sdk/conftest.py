"""Shared pytest configuration for SDK tests."""

from pathlib import Path

import pytest

from rhesis.sdk.services.extractor import SourceSpecification, SourceType


# RHESIS_API_KEY should not be changed as it is used in integration tests auth
@pytest.fixture(autouse=True)
def set_api_keys(monkeypatch):
    """Automatically set API keys for all SDK tests."""
    monkeypatch.setenv("RHESIS_API_KEY", "rh-test-token")
    monkeypatch.setenv("GEMINI_API_KEY", "test_api_key")


# Fixtures for source specifications
@pytest.fixture
def text_source():
    """Fixture for text source specification."""
    return SourceSpecification(
        type=SourceType.TEXT,
        name="test",
        description="test",
        metadata={"content": "test"},
    )


@pytest.fixture
def document_source():
    """Fixture for document source specification."""
    return SourceSpecification(
        type=SourceType.DOCUMENT,
        name="test",
        description="test",
        metadata={"path": Path(__file__).parent / "services" / "test_document.pdf"},
    )


@pytest.fixture
def website_source():
    """Fixture for website source specification."""
    return SourceSpecification(
        type=SourceType.WEBSITE,
        name="test",
        description="test",
        metadata={"url": "https://example.com/test-page"},
    )
