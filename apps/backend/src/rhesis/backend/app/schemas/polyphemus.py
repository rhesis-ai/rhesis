"""Schemas for Polyphemus access control."""

from pydantic import BaseModel, Field


class PolyphemusAccessRequest(BaseModel):
    """Schema for requesting Polyphemus access."""

    justification: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Justification and context for why Polyphemus access is needed",
    )
    expected_monthly_requests: int = Field(
        ...,
        ge=0,
        le=10000,
        description="Expected number of requests per month (0-10,000)",
    )


class PolyphemusAccessResponse(BaseModel):
    """Response schema for Polyphemus access request."""

    success: bool
    message: str
