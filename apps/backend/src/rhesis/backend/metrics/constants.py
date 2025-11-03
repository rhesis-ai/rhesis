import operator
from enum import Enum


class ScoreType(str, Enum):
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"


class ThresholdOperator(str, Enum):
    EQUAL = "="
    LESS_THAN = "<"
    GREATER_THAN = ">"
    LESS_THAN_OR_EQUAL = "<="
    GREATER_THAN_OR_EQUAL = ">="
    NOT_EQUAL = "!="


# Mapping threshold operators to Python operator functions
OPERATOR_MAP = {
    ThresholdOperator.EQUAL: operator.eq,
    ThresholdOperator.LESS_THAN: operator.lt,
    ThresholdOperator.GREATER_THAN: operator.gt,
    ThresholdOperator.LESS_THAN_OR_EQUAL: operator.le,
    ThresholdOperator.GREATER_THAN_OR_EQUAL: operator.ge,
    ThresholdOperator.NOT_EQUAL: operator.ne,
}

# Valid operators for different score types
VALID_OPERATORS_BY_SCORE_TYPE = {
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
