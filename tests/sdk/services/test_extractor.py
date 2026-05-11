from unittest.mock import MagicMock, Mock, patch

import pytest

from rhesis.sdk.services.extractor import (
    DocumentExtractor,
    ExtractionService,
    IdentityExtractor,
    ImageExtractor,
    WebsiteExtractor,
)


# ---------------------------------------------------------------------------
# ImageExtractor — vision model path
# ---------------------------------------------------------------------------


class TestImageExtractorWithModel:
    """ImageExtractor behaviour when a vision model is configured."""

    def _make_extractor(self):
        """Return an ImageExtractor wired to a mock BaseLLM."""
        mock_llm = MagicMock()
        mock_llm.model_name = "mock/vision-model"
        mock_llm.api_key = None
        mock_llm.api_base = None
        mock_llm.api_version = None

        with patch("rhesis.sdk.services.extractor.MarkItDown"):
            extractor = ImageExtractor(model=mock_llm)
        extractor._llm = mock_llm
        extractor._has_model = True
        return extractor, mock_llm

    def test_has_model_flag_set_when_model_provided(self):
        mock_llm = MagicMock()
        mock_llm.model_name = "mock/vision"
        with patch("rhesis.sdk.services.extractor.MarkItDown"):
            ext = ImageExtractor(model=mock_llm)
        assert ext._has_model is True
        assert ext._llm is mock_llm

    def test_has_model_flag_false_when_no_model(self):
        ext = ImageExtractor()
        assert ext._has_model is False
        assert ext._llm is None

    def test_non_image_extension_bypasses_validation_with_model(self):
        """With a model, .pdf must not raise a ValueError for unsupported extension."""
        extractor, _ = self._make_extractor()
        fake_description = "A Kubernetes architecture diagram."

        with patch.object(extractor, "_describe_with_llm", return_value=fake_description):
            result = extractor.extract_from_bytes(b"%PDF-fake", "diagram.pdf")

        assert result == fake_description

    def test_non_image_extension_raises_without_model(self):
        """Without a model, unsupported extension must raise ValueError."""
        ext = ImageExtractor()
        with pytest.raises(ValueError, match="Unsupported image type"):
            ext.extract_from_bytes(b"%PDF-fake", "diagram.pdf")

    def test_image_extension_uses_markitdown_path(self):
        """Even with a model, native image types go through MarkItDown."""
        extractor, _ = self._make_extractor()
        mock_result = MagicMock()
        mock_result.text_content = "A screenshot of a terminal."

        with patch.object(extractor.converter, "convert", return_value=mock_result):
            result = extractor.extract_from_bytes(b"\x89PNG\r\n", "screen.png")

        assert result == "A screenshot of a terminal."


class TestDescribeWithLlm:
    """Unit tests for ImageExtractor._describe_with_llm."""

    def _make_extractor_with_llm(self, mock_llm):
        with patch("rhesis.sdk.services.extractor.MarkItDown"):
            ext = ImageExtractor(model=mock_llm)
        ext._llm = mock_llm
        ext._has_model = True
        return ext

    def test_calls_adapter_with_base64_inline_data(self):
        """_describe_with_llm routes through _MarkItDownModelAdapter._Completions."""
        mock_llm = MagicMock()
        mock_llm.model_name = "vertex_ai/gemini-flash"
        ext = self._make_extractor_with_llm(mock_llm)

        fake_response = MagicMock()
        fake_response.choices[0].message.content = "Slide content here."

        # Patch at the adapter layer — _describe_with_llm uses the adapter now.
        with patch("litellm.completion", return_value=fake_response) as mock_completion:
            result = ext._describe_with_llm(b"fake-pdf-bytes", "application/pdf", "doc.pdf")

        assert result == "Slide content here."
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["model"] == "vertex_ai/gemini-flash"
        messages = call_kwargs["messages"]
        assert len(messages) == 1
        content = messages[0]["content"]
        assert any(
            "data:application/pdf;base64," in item.get("image_url", {}).get("url", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "image_url"
        )

    def test_raises_on_adapter_error(self):
        mock_llm = MagicMock()
        mock_llm.model_name = "mock/model"
        ext = self._make_extractor_with_llm(mock_llm)

        with patch("litellm.completion", side_effect=RuntimeError("connection refused")):
            with pytest.raises(ValueError, match="Vision LLM failed"):
                ext._describe_with_llm(b"bytes", "application/pdf", "doc.pdf")


# ---------------------------------------------------------------------------
# Original extractor tests
# ---------------------------------------------------------------------------


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
    extracted_source = ExtractionService.extract([text_source, document_source])
    assert extracted_source[0].content == "test"
    assert extracted_source[1].content == "Test Rhesis"
