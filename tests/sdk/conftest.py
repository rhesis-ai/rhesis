"""Shared pytest configuration for SDK tests."""

from pathlib import Path

import pytest

from rhesis.sdk.services.extractor import SourceSpecification, SourceType

RHESIS_API_KEY = "rh-local-token"
RHESIS_BASE_URL = "http://test:8000"
GEMINI_API_KEY = "test_api_key"


@pytest.fixture(autouse=True)
def set_api_keys(monkeypatch):
    monkeypatch.setenv("RHESIS_API_KEY", RHESIS_API_KEY)
    monkeypatch.setenv("RHESIS_BASE_URL", RHESIS_BASE_URL)
    monkeypatch.setenv("GEMINI_API_KEY", GEMINI_API_KEY)


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
