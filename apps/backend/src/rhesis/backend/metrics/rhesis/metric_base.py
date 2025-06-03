from typing import List, Optional, Union

from rhesis.backend.metrics.base import BaseMetric, MetricResult, MetricType
# Import the enums and evaluator from the centralized location
from rhesis.backend.metrics.evaluator import ScoreType, ThresholdOperator, MetricEvaluator


class RhesisMetricBase(BaseMetric):
    """Base class for Rhesis' own metrics with common functionality."""

    def __init__(self, name: str, threshold: Optional[float] = None, reference_score: Optional[str] = None, metric_type: MetricType = "rag"):
        super().__init__(name=name, metric_type=metric_type)
        self._threshold = threshold
        self._reference_score = reference_score
        self._evaluator = MetricEvaluator()

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
        Delegates to the evaluator's comprehensive implementation.
        
        Args:
            score: The score to evaluate
            score_type: Type of score (binary, numeric, or categorical)
            threshold: Threshold value for numeric scores (defaults to self.threshold)
            reference_score: Reference score for binary/categorical scores (defaults to self.reference_score)
            threshold_operator: Comparison operator (defaults based on score_type)
            
        Returns:
            bool: True if the score meets the success criteria
        """
        # Use default values from instance if not provided
        if threshold is None:
            threshold = self.threshold
        if reference_score is None:
            reference_score = self.reference_score
            
        # Delegate to the evaluator's comprehensive implementation
        return self._evaluator.evaluate_score(
            score=score,
            threshold=threshold,
            threshold_operator=threshold_operator,
            reference_score=reference_score,
            score_type=score_type
        ) 