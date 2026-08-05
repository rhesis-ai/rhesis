from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class InsightsResponse(BaseModel):
    """Uniform envelope returned by GET /insights and each entry of POST /insights/query."""

    entity: str
    dimensions: List[str]
    measures: List[str]
    rows: List[Dict[str, Any]]


class InsightsQuery(BaseModel):
    """One entity/group_by/measures request -- the body shape of a single
    GET /insights call, reused as one entry in POST /insights/query."""

    entity: str
    group_by: List[str] = Field(default_factory=list)
    measures: List[str] = Field(default_factory=lambda: ["count"])
    filters: Dict[str, List[str]] = Field(default_factory=dict)
    months: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class InsightsIdsResponse(BaseModel):
    """Distinct entity IDs matching Insights filters + optional outcome.

    Same filter universe as GET /insights; different verb (resolve IDs, not
    aggregate). Used for drill-down (e.g. failed-tests list under a chart slice).
    """

    entity: str
    ids: List[str]
