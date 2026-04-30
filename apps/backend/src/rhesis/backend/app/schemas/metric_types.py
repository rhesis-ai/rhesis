"""
Score/threshold enums and operator maps for backend metrics.

Values match `rhesis.sdk.metrics.base` and `rhesis.sdk.metrics.constants` so DB rows
and API payloads stay compatible without importing the full SDK in core installs.
"""

from __future__ import annotations

import operator
from enum import Enum
from typing import Any, Callable, Dict


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
