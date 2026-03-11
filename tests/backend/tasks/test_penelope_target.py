"""Tests for BackendEndpointTarget response metadata propagation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.tasks.execution.penelope_target import BackendEndpointTarget


def _make_target():
    """Create a BackendEndpointTarget bypassing DB validation."""
    db = MagicMock(spec=Session)
    with (
        patch.object(BackendEndpointTarget, "validate_configuration", return_value=(True, None)),
        patch.object(BackendEndpointTarget, "_load_endpoint_metadata"),
    ):
        return BackendEndpointTarget(
            db=db,
            endpoint_id="00000000-0000-0000-0000-000000000001",
            organization_id="org-1",
            user_id="user-1",
        )


@pytest.fixture
def target():
    return _make_target()


class TestBackendEndpointTargetResponseMetadata:
    """Verify that context, metadata, and tool_calls propagate into response_metadata."""

    def _invoke_with_response(self, target, response_data):
        """Invoke send_message with a mocked endpoint service response."""
        mock_service = AsyncMock()
        mock_service.invoke_endpoint.return_value = response_data

        with patch.object(target, "endpoint_service", mock_service):
            return target.send_message("Hello", conversation_id="conv-1")

    def test_tool_calls_propagated(self, target):
        """tool_calls from response_data appear in response_metadata."""
        tool_calls = [{"name": "search", "arguments": {"q": "test"}, "result": "ok"}]
        result = self._invoke_with_response(
            target,
            {
                "output": "Found it.",
                "conversation_id": "conv-1",
                "tool_calls": tool_calls,
            },
        )

        assert result.success is True
        assert result.metadata["tool_calls"] == tool_calls

    def test_context_propagated(self, target):
        """context from response_data appears in response_metadata."""
        context = ["doc1.pdf", "doc2.pdf"]
        result = self._invoke_with_response(
            target,
            {
                "output": "Here's the info.",
                "conversation_id": "conv-1",
                "context": context,
            },
        )

        assert result.success is True
        assert result.metadata["context"] == context

    def test_metadata_propagated(self, target):
        """metadata from response_data appears as endpoint_metadata."""
        metadata = {"model": "gpt-4", "tokens": 42}
        result = self._invoke_with_response(
            target,
            {
                "output": "Response.",
                "conversation_id": "conv-1",
                "metadata": metadata,
            },
        )

        assert result.success is True
        assert result.metadata["endpoint_metadata"] == metadata

    def test_all_fields_propagated_together(self, target):
        """context, metadata, and tool_calls all propagate simultaneously."""
        tool_calls = [{"name": "fn", "arguments": {}, "result": "r"}]
        context = ["source.pdf"]
        metadata = {"confidence": 0.95}

        result = self._invoke_with_response(
            target,
            {
                "output": "Full response.",
                "conversation_id": "conv-1",
                "context": context,
                "metadata": metadata,
                "tool_calls": tool_calls,
            },
        )

        assert result.success is True
        assert result.metadata["context"] == context
        assert result.metadata["endpoint_metadata"] == metadata
        assert result.metadata["tool_calls"] == tool_calls

    def test_missing_fields_not_in_metadata(self, target):
        """When fields are absent, they are not added to response_metadata."""
        result = self._invoke_with_response(
            target,
            {
                "output": "Plain response.",
                "conversation_id": "conv-1",
            },
        )

        assert result.success is True
        assert "context" not in result.metadata
        assert "endpoint_metadata" not in result.metadata
        assert "tool_calls" not in result.metadata

    def test_empty_tool_calls_not_propagated(self, target):
        """Empty tool_calls list is falsy and should not be propagated."""
        result = self._invoke_with_response(
            target,
            {
                "output": "Response.",
                "conversation_id": "conv-1",
                "tool_calls": [],
            },
        )

        assert result.success is True
        assert "tool_calls" not in result.metadata

    def test_none_metadata_not_propagated(self, target):
        """None metadata is not propagated."""
        result = self._invoke_with_response(
            target,
            {
                "output": "Response.",
                "conversation_id": "conv-1",
                "metadata": None,
            },
        )

        assert result.success is True
        assert "endpoint_metadata" not in result.metadata
