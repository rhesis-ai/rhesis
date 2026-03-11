"""
Unit tests for the metadata merging behaviour added to _save_test_set_to_database.

These tests are deliberately narrow and do not exercise the full Celery task
machinery — they only verify that extra_metadata is correctly merged into the
test set payload that would be sent to bulk_create_test_set.
"""

from unittest.mock import MagicMock, patch

import pytest


def _make_sdk_test_set(name="Generated Set", metadata=None):
    """Minimal SDK-like test set object."""
    ts = MagicMock()
    ts.name = name
    ts.description = "Auto-generated"
    ts.short_description = "Short"
    ts.test_set_type = "single_turn"
    ts.metadata = metadata or {}

    # One minimal test so the function doesn't raise "No tests to save"
    test_dict = {
        "prompt": {"content": "hello", "language_code": "en"},
        "behavior": "Harmful",
        "category": "Security",
        "topic": "Injection",
        "metadata": {"generated_by": "ConfigSynthesizer", "additional_info": {}},
    }
    # Make the test behave like a dict
    ts.tests = [test_dict]
    return ts


@pytest.mark.unit
class TestSaveTestSetMetadataMerge:
    """Tests for the extra_metadata merging in _save_test_set_to_database."""

    @patch("rhesis.backend.tasks.test_set.bulk_create_test_set")
    def test_extra_metadata_merged_into_test_set(self, mock_bulk_create):
        """extra_metadata should be merged into the saved test set's metadata."""
        from rhesis.backend.tasks.test_set import _save_test_set_to_database

        # Arrange
        mock_task = MagicMock()
        mock_bulk_create.return_value = MagicMock()

        ts = _make_sdk_test_set(metadata={"existing_key": "existing_value"})
        extra = {
            "source": "garak_dynamic",
            "garak_module": "fitd",
            "garak_tags": ["owasp:llm01"],
        }

        # Act
        _save_test_set_to_database(
            mock_task,
            ts,
            org_id="org-123",
            user_id="user-456",
            extra_metadata=extra,
        )

        # Assert
        call_kwargs = mock_bulk_create.call_args
        test_set_data = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1]["test_set_data"]
        merged = test_set_data["metadata"]

        assert merged["existing_key"] == "existing_value"
        assert merged["source"] == "garak_dynamic"
        assert merged["garak_module"] == "fitd"
        assert merged["garak_tags"] == ["owasp:llm01"]

    @patch("rhesis.backend.tasks.test_set.bulk_create_test_set")
    def test_none_extra_metadata_is_safe(self, mock_bulk_create):
        """Passing extra_metadata=None should not raise and should preserve base metadata."""
        from rhesis.backend.tasks.test_set import _save_test_set_to_database

        mock_task = MagicMock()
        mock_bulk_create.return_value = MagicMock()

        ts = _make_sdk_test_set(metadata={"base": "value"})

        _save_test_set_to_database(
            mock_task,
            ts,
            org_id="org-123",
            user_id="user-456",
            extra_metadata=None,
        )

        call_kwargs = mock_bulk_create.call_args
        test_set_data = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1]["test_set_data"]
        assert test_set_data["metadata"]["base"] == "value"

    @patch("rhesis.backend.tasks.test_set.bulk_create_test_set")
    def test_extra_metadata_overrides_base_keys(self, mock_bulk_create):
        """When base and extra share a key, extra_metadata wins."""
        from rhesis.backend.tasks.test_set import _save_test_set_to_database

        mock_task = MagicMock()
        mock_bulk_create.return_value = MagicMock()

        ts = _make_sdk_test_set(metadata={"source": "original_source"})

        _save_test_set_to_database(
            mock_task,
            ts,
            org_id="org-123",
            user_id="user-456",
            extra_metadata={"source": "garak_dynamic"},
        )

        call_kwargs = mock_bulk_create.call_args
        test_set_data = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1]["test_set_data"]
        assert test_set_data["metadata"]["source"] == "garak_dynamic"
