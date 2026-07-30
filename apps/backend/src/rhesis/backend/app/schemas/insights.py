from typing import Any, Dict, List

from pydantic import BaseModel


class InsightsResponse(BaseModel):
    """Uniform envelope returned by GET /insights, regardless of entity."""

    entity: str
    dimensions: List[str]
    measures: List[str]
    rows: List[Dict[str, Any]]
