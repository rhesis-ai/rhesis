from typing import Dict, Optional

from pydantic import BaseModel


class DimensionStats(BaseModel):
    dimension: str
    total: int
    breakdown: Dict[str, int]


class HistoricalStats(BaseModel):
    period: str
    start_date: str
    end_date: str
    monthly_counts: Dict[str, int]


class EntityStats(BaseModel):
    total: int
    stats: Dict[str, DimensionStats]
    metadata: Optional[Dict] = None
    history: Optional[HistoricalStats] = None
