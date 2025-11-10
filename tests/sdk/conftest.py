from pathlib import Path

import pytest

from rhesis.sdk.services.extractor import SourceSpecification, SourceType


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
