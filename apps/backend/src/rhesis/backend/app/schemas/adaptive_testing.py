"""Schemas for adaptive testing API (generate outputs, etc.)."""

from typing import List, Optional

from pydantic import UUID4, BaseModel

from rhesis.backend.app.schemas import Base


class GenerateOutputsRequest(Base):
    """Request body for generating test outputs via endpoint invocation."""

    endpoint_id: UUID4
    test_ids: Optional[List[UUID4]] = None
    topic: Optional[str] = None
    include_subtopics: bool = True


class GenerateOutputsUpdatedItem(BaseModel):
    """One test whose output was updated (stored in test_metadata)."""

    test_id: str
    output: str


class GenerateOutputsFailedItem(BaseModel):
    """One test that failed during output generation."""

    test_id: str
    error: str


class GenerateOutputsResponse(Base):
    """Response for generate outputs. Results are stored in test metadata."""

    generated: int
    failed: List[GenerateOutputsFailedItem]
    updated: List[GenerateOutputsUpdatedItem]
