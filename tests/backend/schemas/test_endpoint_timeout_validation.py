"""Tests for timeout_seconds validation on endpoint schemas."""

import pytest
from pydantic import ValidationError

from rhesis.backend.app.schemas.endpoint import (
    Endpoint,
    EndpointCreate,
    EndpointMetadata,
    EndpointUpdate,
)


class TestTimeoutSecondsValidation:
    """Validate timeout_seconds bounds on create/update schemas."""

    def test_none_is_accepted(self):
        data = EndpointCreate(
            name="ep", connection_type="REST", timeout_seconds=None
        )
        assert data.timeout_seconds is None

    def test_valid_value_accepted(self):
        data = EndpointCreate(
            name="ep", connection_type="REST", timeout_seconds=60
        )
        assert data.timeout_seconds == 60

    def test_boundary_min(self):
        data = EndpointCreate(
            name="ep", connection_type="REST", timeout_seconds=1
        )
        assert data.timeout_seconds == 1

    def test_boundary_max(self):
        data = EndpointCreate(
            name="ep", connection_type="REST", timeout_seconds=3600
        )
        assert data.timeout_seconds == 3600

    def test_zero_rejected(self):
        with pytest.raises(ValidationError, match="timeout_seconds must be between 1 and 3600"):
            EndpointCreate(name="ep", connection_type="REST", timeout_seconds=0)

    def test_negative_rejected(self):
        with pytest.raises(ValidationError, match="timeout_seconds must be between 1 and 3600"):
            EndpointCreate(name="ep", connection_type="REST", timeout_seconds=-5)

    def test_over_max_rejected(self):
        with pytest.raises(ValidationError, match="timeout_seconds must be between 1 and 3600"):
            EndpointCreate(name="ep", connection_type="REST", timeout_seconds=3601)

    def test_update_schema_validates_too(self):
        with pytest.raises(ValidationError, match="timeout_seconds must be between 1 and 3600"):
            EndpointUpdate(timeout_seconds=0)

    def test_update_schema_accepts_valid(self):
        data = EndpointUpdate(timeout_seconds=120)
        assert data.timeout_seconds == 120


class TestResponseSchemaExtractsTimeout:
    """Validate model_validator on the response schema pulls timeout from metadata."""

    _VALID_UUID = "a0000000-0000-4000-8000-000000000001"

    def test_extracts_timeout_from_metadata_dict(self):
        ep = Endpoint.model_validate(
            {
                "id": self._VALID_UUID,
                "name": "ep",
                "connection_type": "REST",
                "endpoint_metadata": {"timeout_seconds": 45},
            }
        )
        assert ep.timeout_seconds == 45

    def test_explicit_field_wins_over_metadata(self):
        ep = Endpoint.model_validate(
            {
                "id": self._VALID_UUID,
                "name": "ep",
                "connection_type": "REST",
                "timeout_seconds": 90,
                "endpoint_metadata": {"timeout_seconds": 45},
            }
        )
        assert ep.timeout_seconds == 90

    def test_no_metadata_returns_none(self):
        ep = Endpoint.model_validate(
            {
                "id": self._VALID_UUID,
                "name": "ep",
                "connection_type": "REST",
            }
        )
        assert ep.timeout_seconds is None


class TestEndpointMetadataValidation:
    """Validate EndpointMetadata model and its sub-models."""

    def test_timeout_inside_metadata_validated(self):
        """Invalid timeout_seconds inside endpoint_metadata is rejected."""
        with pytest.raises(ValidationError, match="timeout_seconds must be between 1 and 3600"):
            EndpointCreate(
                name="ep",
                connection_type="REST",
                endpoint_metadata={"timeout_seconds": 5000},
            )

    def test_valid_timeout_inside_metadata(self):
        ep = EndpointCreate(
            name="ep",
            connection_type="REST",
            endpoint_metadata={"timeout_seconds": 120},
        )
        assert ep.endpoint_metadata.timeout_seconds == 120

    def test_confidence_range_validated(self):
        with pytest.raises(ValidationError, match="confidence must be between 0.0 and 1.0"):
            EndpointCreate(
                name="ep",
                connection_type="REST",
                endpoint_metadata={"mapping_info": {"confidence": 1.5}},
            )

    def test_valid_confidence(self):
        ep = EndpointCreate(
            name="ep",
            connection_type="REST",
            endpoint_metadata={"mapping_info": {"confidence": 0.85, "source": "auto_mapped"}},
        )
        assert ep.endpoint_metadata.mapping_info.confidence == 0.85

    def test_extra_keys_preserved(self):
        ep = EndpointCreate(
            name="ep",
            connection_type="REST",
            endpoint_metadata={"custom_flag": True, "timeout_seconds": 30},
        )
        assert ep.endpoint_metadata.timeout_seconds == 30
        assert ep.endpoint_metadata.model_dump()["custom_flag"] is True

    def test_serialization_strips_none(self):
        meta = EndpointMetadata(timeout_seconds=60)
        dumped = meta.model_dump()
        assert dumped == {"timeout_seconds": 60}
        assert "sdk_connection" not in dumped

    def test_nested_model_strips_none(self):
        meta = EndpointMetadata(
            sdk_connection={"function_name": "my_func"},
        )
        dumped = meta.model_dump()
        assert dumped == {"sdk_connection": {"function_name": "my_func"}}
        assert "project_id" not in dumped["sdk_connection"]

    def test_full_metadata_round_trip(self):
        raw = {
            "sdk_connection": {"function_name": "test", "project_id": "abc"},
            "function_schema": {"description": "A test func", "parameters": {"x": {"type": "str"}}},
            "mapping_info": {"source": "auto_mapped", "confidence": 0.9},
            "timeout_seconds": 60,
        }
        meta = EndpointMetadata.model_validate(raw)
        dumped = meta.model_dump()
        assert dumped["sdk_connection"]["function_name"] == "test"
        assert dumped["function_schema"]["parameters"] == {"x": {"type": "str"}}
        assert dumped["mapping_info"]["confidence"] == 0.9
        assert dumped["timeout_seconds"] == 60
