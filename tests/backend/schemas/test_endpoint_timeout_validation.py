"""Tests for timeout_seconds validation on endpoint schemas."""

import pytest
from pydantic import ValidationError

from rhesis.backend.app.schemas.endpoint import Endpoint, EndpointCreate, EndpointUpdate


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
