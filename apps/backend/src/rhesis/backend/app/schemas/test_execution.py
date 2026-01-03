"""Schemas for test execution context."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TestExecutionContext(BaseModel):
    """
    Test execution context with proper UUID types.

    This context is added by the backend during test execution and flows
    through to SDK telemetry spans for trace linking. All IDs are UUIDs.

    Flow:
    1. Backend executor creates this context
    2. SDK invoker injects it as _rhesis_test_context
    3. SDK executor extracts it and stores in context variable
    4. SDK tracer reads from context variable and adds as span attributes
    5. User function never sees this parameter
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "test_run_id": "550e8400-e29b-41d4-a716-446655440000",
                "test_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                "test_configuration_id": "6ba7b814-9dad-11d1-80b4-00c04fd430c8",
                "test_result_id": None,
            }
        }
    )

    test_run_id: UUID = Field(..., description="Test run identifier (UUID)")
    test_id: UUID = Field(..., description="Individual test identifier (UUID)")
    test_configuration_id: UUID = Field(..., description="Test configuration identifier (UUID)")
    test_result_id: Optional[UUID] = Field(
        None, description="Test result ID (UUID, created after execution completes)"
    )
