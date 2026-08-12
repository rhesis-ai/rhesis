"""
Tests for SDK endpoint status handling in
rhesis.backend.app.services.endpoint.validation

Registration no longer invokes the agent to validate its mappings, so an
endpoint marked Error by the old flow must not keep showing that error once it
is marked Active again on the next reconnect.
"""

import uuid
from unittest.mock import Mock, patch

import pytest

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.services.endpoint.validation import validate_and_update_status


def _make_endpoint(metadata=None) -> Endpoint:
    """Build a transient endpoint carrying the given metadata."""
    return Endpoint(
        name="sdk-endpoint",
        connection_type="SDK",
        endpoint_metadata=metadata,
    )


async def _run(endpoint: Endpoint, status=None):
    """Invoke validate_and_update_status with get_or_create_status stubbed."""
    with patch(
        "rhesis.backend.app.services.endpoint.validation.get_or_create_status",
        return_value=status,
    ):
        return await validate_and_update_status(
            db=Mock(),
            endpoint=endpoint,
            project_id=str(uuid.uuid4()),
            environment="development",
            function_name="chat",
            organization_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
        )


class TestValidateAndUpdateStatus:
    """Status handling for freshly registered SDK endpoints."""

    @pytest.mark.asyncio
    async def test_marks_endpoint_active(self):
        """The endpoint is stamped with the Active status."""
        status = Mock(id=uuid.uuid4())
        endpoint = _make_endpoint()

        result = await _run(endpoint, status)

        assert result == {"success": True, "error": None, "status_set": "Active"}
        assert endpoint.status_id == status.id

    @pytest.mark.asyncio
    async def test_clears_stale_validation_errors(self):
        """Error metadata from the removed validation flow is dropped."""
        endpoint = _make_endpoint(
            {
                "validation_error": {"error": "mapping failed", "reason": "bad_mapping"},
                "last_error": "mapping failed",
            }
        )

        await _run(endpoint, Mock(id=uuid.uuid4()))

        assert "validation_error" not in endpoint.endpoint_metadata
        assert "last_error" not in endpoint.endpoint_metadata

    @pytest.mark.asyncio
    async def test_preserves_unrelated_metadata(self):
        """Only the error keys are removed; the rest of the metadata survives."""
        endpoint = _make_endpoint(
            {
                "last_error": "mapping failed",
                "sdk_connection": {"function_name": "chat"},
                "mapping_info": {"source": "auto_mapped"},
            }
        )

        await _run(endpoint, Mock(id=uuid.uuid4()))

        assert endpoint.endpoint_metadata == {
            "sdk_connection": {"function_name": "chat"},
            "mapping_info": {"source": "auto_mapped"},
        }

    @pytest.mark.asyncio
    async def test_handles_missing_metadata(self):
        """An endpoint with no metadata is marked Active without error."""
        endpoint = _make_endpoint(None)

        result = await _run(endpoint, Mock(id=uuid.uuid4()))

        assert result["success"] is True
        assert endpoint.endpoint_metadata is None

    @pytest.mark.asyncio
    async def test_leaves_metadata_when_status_lookup_fails(self):
        """No Active status means the endpoint keeps its previous state."""
        endpoint = _make_endpoint({"last_error": "mapping failed"})

        result = await _run(endpoint, None)

        assert result["success"] is True
        assert endpoint.status_id is None
        assert endpoint.endpoint_metadata == {"last_error": "mapping failed"}
