"""
Tests for rhesis.backend.app.services.endpoint.files

Covers:
- endpoint_supports_files   — request_mapping detection
- inject_file_content_into_input — message augmentation
- enrich_files_with_extraction   — extraction pipeline incl. vision fallback
"""

import base64
from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.services.endpoint.files import (
    endpoint_supports_files,
    enrich_files_with_extraction,
    inject_file_content_into_input,
)


# ---------------------------------------------------------------------------
# endpoint_supports_files
# ---------------------------------------------------------------------------


class TestEndpointSupportsFiles:
    def _endpoint(self, mapping):
        ep = MagicMock()
        ep.request_mapping = mapping
        return ep

    def test_returns_true_when_files_template_present(self):
        ep = self._endpoint({"files": "{{ files }}"})
        assert endpoint_supports_files(ep) is True

    def test_returns_true_with_extra_whitespace_in_template(self):
        ep = self._endpoint({"files": "{{  files  }}"})
        assert endpoint_supports_files(ep) is True

    def test_returns_false_when_no_files_template(self):
        ep = self._endpoint({"message": "{{ input }}"})
        assert endpoint_supports_files(ep) is False

    def test_returns_false_when_mapping_is_none(self):
        ep = self._endpoint(None)
        assert endpoint_supports_files(ep) is False

    def test_returns_false_when_mapping_is_empty(self):
        ep = self._endpoint({})
        assert endpoint_supports_files(ep) is False

    def test_works_with_string_mapping(self):
        ep = self._endpoint('{"files": "{{ files }}"}')
        assert endpoint_supports_files(ep) is True


# ---------------------------------------------------------------------------
# inject_file_content_into_input
# ---------------------------------------------------------------------------


class TestInjectFileContentIntoInput:
    def test_appends_file_content_to_message(self):
        files = [{"filename": "report.pdf", "extracted_text": "Revenue was $5M."}]
        result = inject_file_content_into_input("Summarise this", files)
        assert "Summarise this" in result
        assert "report.pdf" in result
        assert "Revenue was $5M." in result

    def test_uses_placeholder_when_extracted_text_empty(self):
        files = [{"filename": "scan.png", "extracted_text": ""}]
        result = inject_file_content_into_input("What is this?", files)
        assert "[File content could not be extracted]" in result

    def test_uses_placeholder_when_extracted_text_missing(self):
        files = [{"filename": "scan.png"}]
        result = inject_file_content_into_input("What is this?", files)
        assert "[File content could not be extracted]" in result

    def test_multiple_files_all_included(self):
        files = [
            {"filename": "a.txt", "extracted_text": "Content A"},
            {"filename": "b.txt", "extracted_text": "Content B"},
        ]
        result = inject_file_content_into_input("Explain", files)
        assert "a.txt" in result
        assert "Content A" in result
        assert "b.txt" in result
        assert "Content B" in result

    def test_empty_files_list_returns_original_input(self):
        result = inject_file_content_into_input("Hello", [])
        assert result == "Hello"

    def test_original_message_is_preserved_verbatim(self):
        files = [{"filename": "f.pdf", "extracted_text": "stuff"}]
        msg = "What is in this file? Please be detailed."
        result = inject_file_content_into_input(msg, files)
        assert result.startswith(msg)


# ---------------------------------------------------------------------------
# enrich_files_with_extraction
# ---------------------------------------------------------------------------


# files.py imports resolve_model_for_extraction from model_resolution; patch there.
_FILES_PATH = "rhesis.backend.app.services.endpoint.files"
# output_providers still has _resolve_model_for_extraction as a re-exported alias.
_PROVIDERS_PATH = "rhesis.backend.tasks.execution.executors.output_providers"
_SDK_EXTRACTOR_PATH = "rhesis.sdk.services.extractor"


class TestEnrichFilesWithExtraction:
    """Unit tests for enrich_files_with_extraction.

    The extraction strategy is now fully encapsulated in
    ``extract_with_vision_fallback`` (SDK), so these tests mock that single
    entry-point rather than the internal _select_extractor / ImageExtractor
    chain.  Model resolution is mocked at the site where files.py looks it
    up (model_resolution module) to keep tests DB-free.
    """

    def _file_dict(self, filename="doc.txt", content_type="text/plain", data=None):
        return {
            "filename": filename,
            "content_type": content_type,
            "data": base64.b64encode(data or b"hello").decode("ascii"),
        }

    def test_fast_path_all_files_already_have_text(self):
        """When all files already have extracted_text, model resolution is skipped entirely."""
        files = [
            {"filename": "a.txt", "data": "x", "extracted_text": "text A"},
            {"filename": "b.txt", "data": "y", "extracted_text": "text B"},
        ]
        with patch(f"{_FILES_PATH}.resolve_model_for_extraction") as mock_resolve:
            result = enrich_files_with_extraction(files, db=None, user_id=None)
        mock_resolve.assert_not_called()
        assert result == files

    @patch(f"{_FILES_PATH}.resolve_model_for_extraction")
    def test_skips_individual_file_that_already_has_extracted_text(self, mock_resolve):
        mock_resolve.return_value = None
        pre_extracted = {"filename": "done.txt", "data": "x", "extracted_text": "already done"}
        new_file = self._file_dict("new.txt")

        with patch(f"{_SDK_EXTRACTOR_PATH}.extract_with_vision_fallback", return_value="fresh"):
            result = enrich_files_with_extraction([pre_extracted, new_file], db=None, user_id=None)

        assert result[0]["extracted_text"] == "already done"
        assert result[1]["extracted_text"] == "fresh"

    @patch(f"{_FILES_PATH}.resolve_model_for_extraction")
    def test_extracts_text_via_vision_fallback(self, mock_resolve):
        mock_resolve.return_value = None

        with patch(
            f"{_SDK_EXTRACTOR_PATH}.extract_with_vision_fallback", return_value="Extracted content"
        ):
            result = enrich_files_with_extraction([self._file_dict()], db=None, user_id=None)

        assert result[0]["extracted_text"] == "Extracted content"

    @patch(f"{_FILES_PATH}.resolve_model_for_extraction")
    def test_passes_through_non_dict_entries(self, mock_resolve):
        mock_resolve.return_value = None
        result = enrich_files_with_extraction(["not-a-dict"], db=None, user_id=None)
        assert result == ["not-a-dict"]

    def test_model_forwarded_to_extract_with_vision_fallback(self):
        """The resolved model must be forwarded so the vision fallback can fire."""
        mock_model = MagicMock()
        mock_user = MagicMock()

        with (
            patch("rhesis.backend.app.crud.get_user_by_id", return_value=mock_user),
            patch(
                "rhesis.backend.app.utils.user_model_utils.get_user_generation_model",
                return_value="openai/gpt-4o",
            ),
            patch(f"{_FILES_PATH}.resolve_model_for_extraction", return_value=mock_model),
            patch(
                f"{_SDK_EXTRACTOR_PATH}.extract_with_vision_fallback", return_value="diagram"
            ) as mock_fn,
        ):
            enrich_files_with_extraction(
                [self._file_dict("slide.pdf", "application/pdf")],
                db=MagicMock(),
                user_id="user-123",
            )

        _, call_kwargs = mock_fn.call_args
        assert call_kwargs.get("model") is mock_model or mock_fn.call_args[0][3] is mock_model
