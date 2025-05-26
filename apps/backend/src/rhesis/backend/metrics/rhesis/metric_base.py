from typing import List, Optional, Union
from enum import Enum
import operator

from rhesis.backend.metrics.base import BaseMetric, MetricResult, MetricType


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
    ScoreType.BINARY: {ThresholdOperator.EQUAL, ThresholdOperator.NOT_EQUAL},
    ScoreType.CATEGORICAL: {ThresholdOperator.EQUAL, ThresholdOperator.NOT_EQUAL},
    ScoreType.NUMERIC: set(ThresholdOperator),  # All operators are valid for numeric
}


class RhesisMetricBase(BaseMetric):
    """Base class for Rhesis' own metrics with common functionality."""

    def __init__(self, name: str, threshold: Optional[float] = None, reference_score: Optional[str] = None, metric_type: MetricType = "rag"):
        super().__init__(name=name, metric_type=metric_type)
        self._threshold = threshold
        self._reference_score = reference_score

    @property
    def threshold(self) -> Optional[float]:
        return self._threshold

    @threshold.setter
    def threshold(self, value: Optional[float]):
        # No range validation - let the derived classes handle threshold validation if needed
        self._threshold = value
    
    @property
    def reference_score(self) -> Optional[str]:
        return self._reference_score

    @reference_score.setter
    def reference_score(self, value: Optional[str]):
        self._reference_score = value
    
    def _sanitize_threshold_operator(self, threshold_operator: Union[ThresholdOperator, str, None]) -> ThresholdOperator:
        """
        Sanitize and validate the threshold operator.
        
        Args:
            threshold_operator: The threshold operator to sanitize
            
        Returns:
            ThresholdOperator: Sanitized and validated threshold operator
            
        Raises:
            ValueError: If the operator is invalid
        """
        if threshold_operator is None:
            return None
            
        # Trim whitespace if it's a string
        if isinstance(threshold_operator, str):
            threshold_operator = threshold_operator.strip()
            
        # Convert string to enum if needed
        if isinstance(threshold_operator, str):
            try:
                threshold_operator = ThresholdOperator(threshold_operator)
            except ValueError:
                raise ValueError(f"Invalid threshold operator: '{threshold_operator}'. "
                               f"Valid operators are: {', '.join([op.value for op in ThresholdOperator])}")
        
        # Validate that it's a valid ThresholdOperator
        if not isinstance(threshold_operator, ThresholdOperator):
            raise ValueError(f"threshold_operator must be a ThresholdOperator enum or valid string, "
                           f"got {type(threshold_operator)}")
            
        return threshold_operator
    
    def _validate_operator_for_score_type(self, threshold_operator: ThresholdOperator, score_type: ScoreType) -> None:
        """
        Validate that the threshold operator is appropriate for the score type.
        
        Args:
            threshold_operator: The threshold operator to validate
            score_type: The score type to validate against
            
        Raises:
            ValueError: If the operator is not valid for the score type
        """
        valid_operators = VALID_OPERATORS_BY_SCORE_TYPE.get(score_type, set())
        if threshold_operator not in valid_operators:
            valid_ops_str = ', '.join([op.value for op in valid_operators])
            raise ValueError(f"Operator '{threshold_operator.value}' is not valid for score type '{score_type.value}'. "
                           f"Valid operators for {score_type.value} are: {valid_ops_str}")
    
    def evaluate_score(
        self, 
        score: Union[float, str, int], 
        score_type: Union[ScoreType, str], 
        threshold: Optional[float] = None, 
        reference_score: Optional[str] = None,
        threshold_operator: Union[ThresholdOperator, str] = None
    ) -> bool:
        """
        Evaluate if a score meets the success criteria based on score type and threshold operator.
        
        Args:
            score: The score to evaluate
            score_type: Type of score (binary, numeric, or categorical)
            threshold: Threshold value for numeric scores (defaults to self.threshold)
            reference_score: Reference score for binary/categorical scores (defaults to self.reference_score)
            threshold_operator: Comparison operator (defaults based on score_type)
            
        Returns:
            bool: True if the score meets the success criteria
            
        Raises:
            ValueError: If the threshold operator is invalid or inappropriate for the score type
        """
        # Convert string enums to enum values if needed
        if isinstance(score_type, str):
            score_type = ScoreType(score_type)
            
        # Sanitize and validate threshold operator
        threshold_operator = self._sanitize_threshold_operator(threshold_operator)
            
        # Set default threshold operator based on score type
        if threshold_operator is None:
            if score_type == ScoreType.NUMERIC:
                threshold_operator = ThresholdOperator.GREATER_THAN_OR_EQUAL
            else:  # BINARY or CATEGORICAL
                threshold_operator = ThresholdOperator.EQUAL
        
        # Validate operator for score type
        self._validate_operator_for_score_type(threshold_operator, score_type)
        
        # Handle different score types
        if score_type == ScoreType.NUMERIC:
            # For numeric scores, use threshold
            if threshold is None:
                threshold = self.threshold
            if threshold is None:
                raise ValueError("Threshold is required for numeric score type but was not provided")
            
            # Use operator module for comparison
            op_func = OPERATOR_MAP.get(threshold_operator)
            if op_func is None:
                # Fallback to default behavior
                return score >= threshold
                
            return op_func(score, threshold)
            
        else:  # BINARY or CATEGORICAL
            # For binary/categorical scores, use reference_score
            if reference_score is None:
                reference_score = self.reference_score
            if reference_score is None:
                raise ValueError(f"Reference score is required for {score_type.value} score type but was not provided")
            
            # Convert score to string for comparison if needed
            score_str = str(score).lower().strip() if not isinstance(score, str) else score.lower().strip()
            reference_str = reference_score.lower().strip()
            
            # Use operator module for comparison
            op_func = OPERATOR_MAP.get(threshold_operator)
            if op_func is None:
                # Fallback to equality check
                return score_str == reference_str
                
            return op_func(score_str, reference_str) 