"""Configuration and data classes for statistics calculations."""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Type


@dataclass
class StatsConfig:
    """Configuration for stats calculations"""

    default_top_items: Optional[int] = None
    default_months: int = 6
    enable_timing: bool = False
    enable_debug_logging: bool = False


@dataclass
class DimensionInfo:
    """Information about a model dimension"""

    name: str
    model: Type
    join_column: Any
    entity_column: Any
    extra_filters: Optional[Any] = None


@dataclass
class StatsResult:
    """Result structure for stats calculations"""

    total: int
    stats: Dict[str, Any]
    history: Dict[str, Any]
    metadata: Dict[str, Any]
