"""
Score/threshold enums and operator maps for backend metrics.

Values match `rhesis.sdk.metrics.base` and `rhesis.sdk.metrics.constants` so DB rows
and API payloads stay compatible without importing the full SDK in core installs.
"""

from __future__ import annotations

import operator
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ScoreType(str, Enum):
    BINARY = "binary"
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"


class ThresholdOperator(str, Enum):
    EQUAL = "="
    LESS_THAN = "<"
    GREATER_THAN = ">"
    LESS_THAN_OR_EQUAL = "<="
    GREATER_THAN_OR_EQUAL = ">="
    NOT_EQUAL = "!="


# Mapping threshold operators to Python operator functions (same as SDK)
OPERATOR_MAP: Dict[ThresholdOperator, Callable[[Any, Any], bool]] = {
    ThresholdOperator.EQUAL: operator.eq,
    ThresholdOperator.LESS_THAN: operator.lt,
    ThresholdOperator.GREATER_THAN: operator.gt,
    ThresholdOperator.LESS_THAN_OR_EQUAL: operator.le,
    ThresholdOperator.GREATER_THAN_OR_EQUAL: operator.ge,
    ThresholdOperator.NOT_EQUAL: operator.ne,
}

# Valid operators for different score types (same as SDK)
VALID_OPERATORS_BY_SCORE_TYPE = {
    ScoreType.BINARY: {ThresholdOperator.EQUAL, ThresholdOperator.NOT_EQUAL},
    ScoreType.CATEGORICAL: {ThresholdOperator.EQUAL, ThresholdOperator.NOT_EQUAL},
    ScoreType.NUMERIC: set(ThresholdOperator),
}


def check_score_fields(
    score_type: Optional[ScoreType],
    *,
    min_score: Optional[float],
    max_score: Optional[float],
    threshold: Optional[float],
    categories: Optional[List[str]],
    passing_categories: Optional[List[str]],
    partial: bool = False,
) -> None:
    """Raise ValueError when a metric can't be saved with these score fields.

    The range rules apply to numeric metrics and the category rules to categorical
    ones, so stray fields of the other kind are not refused. ``partial`` is an update:
    a field it doesn't send isn't required, a rule is checked only when every field it
    compares is sent, and with no score_type sent both kinds of rule apply. The SDK's
    ``GeneratedMetric`` mirrors these rules (tests/backend/schemas/test_metric_score_rules.py
    checks both).
    """
    # An update that doesn't send score_type is checked as whichever type its fields are for.
    unknown_type = partial and score_type is None
    if score_type == ScoreType.NUMERIC or unknown_type:
        if not partial:
            for field, value in (
                ("min_score", min_score),
                ("max_score", max_score),
                ("threshold", threshold),
            ):
                if value is None:
                    raise ValueError(f"{field} is required for numeric metrics")
        if min_score is not None and max_score is not None:
            if min_score >= max_score:
                raise ValueError("min_score must be below max_score")
            if threshold is not None and not min_score <= threshold <= max_score:
                raise ValueError("threshold must lie between min_score and max_score")

    if score_type != ScoreType.CATEGORICAL and not unknown_type:
        return
    if not partial:
        if not categories or len(categories) < 2:
            raise ValueError("at least 2 categories are required for categorical metrics")
        if not passing_categories:
            raise ValueError("at least 1 passing category is required for categorical metrics")
    if categories is not None and passing_categories is not None:
        unknown = [c for c in passing_categories if c not in categories]
        if unknown:
            raise ValueError(f"passing_categories must be among categories, not {unknown}")
