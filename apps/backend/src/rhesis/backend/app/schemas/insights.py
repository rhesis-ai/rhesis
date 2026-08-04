from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class InsightsResponse(BaseModel):
    """Uniform envelope returned by GET /insights, regardless of entity."""

    entity: str
    dimensions: List[str]
    measures: List[str]
    rows: List[Dict[str, Any]]


class InsightsQuery(BaseModel):
    """One entity/group_by/measures request -- the body shape of a single
    GET /insights call, reused as one entry in an InsightsBatchRequest."""

    entity: str
    group_by: List[str] = Field(default_factory=list)
    measures: List[str] = Field(default_factory=lambda: ["count"])
    filters: Dict[str, List[str]] = Field(default_factory=dict)
    months: int = 6
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class InsightsBatchRequest(BaseModel):
    """Named sub-queries to run in one call. Each one still runs as its own
    single-entity, single-grain query -- see services/insights/query_builder.py."""

    queries: Dict[str, InsightsQuery]


class InsightsBatchResponse(BaseModel):
    """One InsightsResponse per label from the request."""

    results: Dict[str, InsightsResponse]
