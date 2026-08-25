import operator
from typing import Any, Callable, Dict

from rhesis.sdk.metrics.base import ScoreType, ThresholdOperator

# Mapping threshold operators to Python operator functions
OPERATOR_MAP: Dict[ThresholdOperator, Callable[[Any, Any], bool]] = {
    ThresholdOperator.EQUAL: operator.eq,
    ThresholdOperator.LESS_THAN: operator.lt,
    ThresholdOperator.GREATER_THAN: operator.gt,
    ThresholdOperator.LESS_THAN_OR_EQUAL: operator.le,
    ThresholdOperator.GREATER_THAN_OR_EQUAL: operator.ge,
    ThresholdOperator.NOT_EQUAL: operator.ne,
}

# Valid operators for different score types
VALID_OPERATORS_BY_SCORE_TYPE = {
    ScoreType.BINARY: {ThresholdOperator.EQUAL, ThresholdOperator.NOT_EQUAL},
    ScoreType.CATEGORICAL: {ThresholdOperator.EQUAL, ThresholdOperator.NOT_EQUAL},
    ScoreType.NUMERIC: set(ThresholdOperator),  # All operators are valid for numeric
}

# Legacy mapping for string operators (for backward compatibility)
THRESHOLD_OPERATOR_MAP = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "=": operator.eq,
    "==": operator.eq,
    "!=": operator.ne,
    "<>": operator.ne,
}

#: Sampling temperature for LLM-as-judge calls.
#:
#: Judges are measurement, not generation. The provider default (0.7 on the native provider) is
#: right for synthesizers, which want varied tests, but it means the same conversation can score
#: differently on two runs of the same metric, and a re-score can disagree with the live run that
#: produced the trace. Every judge passes this explicitly rather than changing the provider
#: default, which generation legitimately relies on.
JUDGE_TEMPERATURE = 0.0
