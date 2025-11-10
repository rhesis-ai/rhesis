from unittest.mock import Mock, patch

from rhesis.sdk.services.extractor import (
    DocumentExtractor,
    ExtractionService,
    IdentityExtractor,
    WebsiteExtractor,
)


# Tests using fixtures
def test_identity_extractor(text_source):
    extractor = IdentityExtractor()
    extracted_source = extractor.extract(text_source)
    assert extracted_source.content == "test"
    assert extracted_source.metadata is None


def test_document_extractor(document_source):
    extractor = DocumentExtractor()
    extracted_source = extractor.extract(document_source)
    assert extracted_source.content == "Test Rhesis"


def test_website_extractor(website_source):
    mock_response = Mock()
    mock_response.content = b"<html><body><h1>Test Rhesis</h1></body></html>"
    mock_response.status_code = 200

    with patch("rhesis.sdk.services.extractor.requests.get", return_value=mock_response):
        extractor = WebsiteExtractor()
        extracted_source = extractor.extract(website_source)
        assert extracted_source.content == "# Test Rhesis"


def test_extraction_service(text_source, document_source):
    extractor = ExtractionService()
    extracted_source = extractor([text_source, document_source])
    assert extracted_source[0].content == "test"
    assert extracted_source[1].content == "Test Rhesis"
