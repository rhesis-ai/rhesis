from typing import Optional, Union

from rhesis.sdk.metrics.base import BaseMetric, MetricType
from rhesis.sdk.metrics.constants import ScoreType, ThresholdOperator
from rhesis.sdk.metrics.score_evaluator import ScoreEvaluator


class RhesisMetricBase(BaseMetric):
    """Base class for Rhesis' own metrics with common functionality."""

    def __init__(
        self,
        name: str,
        threshold: Optional[float] = None,
        reference_score: Optional[str] = None,
        metric_type: MetricType = "rag",
    ):
        super().__init__(name=name, metric_type=metric_type)
        self._threshold = threshold
        self._reference_score = reference_score
        self._score_evaluator = ScoreEvaluator()

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

    def _sanitize_threshold_operator(
        self, threshold_operator: Union[ThresholdOperator, str, None]
    ) -> Optional[ThresholdOperator]:
        """
        Sanitize and validate the threshold operator.
        Delegates to the score evaluator's implementation.

        Args:
            threshold_operator: The threshold operator to sanitize

        Returns:
            ThresholdOperator: Sanitized and validated threshold operator, or None if invalid

        Raises:
            ValueError: If the operator is invalid
        """
        result = self._score_evaluator._sanitize_threshold_operator(threshold_operator)
        if result is None and threshold_operator is not None:
            raise ValueError(f"Invalid threshold operator: {threshold_operator}")
        return result

    def _validate_operator_for_score_type(
        self, threshold_operator: ThresholdOperator, score_type: ScoreType
    ) -> bool:
        """
        Validate that the threshold operator is appropriate for the score type.
        Delegates to the score evaluator's implementation and raises exception if invalid.

        Args:
            threshold_operator: The threshold operator to validate
            score_type: The score type to validate against

        Returns:
            bool: True if the operator is valid for the score type

        Raises:
            ValueError: If the operator is not valid for the score type
        """
        is_valid = self._score_evaluator._validate_operator_for_score_type(
            threshold_operator, score_type
        )
        if not is_valid:
            from rhesis.sdk.metrics.constants import VALID_OPERATORS_BY_SCORE_TYPE

            valid_operators = VALID_OPERATORS_BY_SCORE_TYPE.get(score_type, set())
            valid_ops_str = ", ".join([op.value for op in valid_operators])
            raise ValueError(
                f"Operator '{threshold_operator.value}' is not valid"
                f"for score type '{score_type.value}'. "
                f"Valid operators for {score_type.value} are: {valid_ops_str}"
            )
        return is_valid

    def evaluate_score(
        self,
        score: Union[float, str, int],
        score_type: Union[ScoreType, str],
        threshold: Optional[float] = None,
        reference_score: Optional[str] = None,
        threshold_operator: Union[ThresholdOperator, str] = None,
    ) -> bool:
        """
        Evaluate if a score meets the success criteria based on score type and threshold operator.
        Delegates to the score evaluator's comprehensive implementation.

        Args:
            score: The score to evaluate
            score_type: Type of score (binary, numeric, or categorical)
            threshold: Threshold value for numeric scores (defaults to self.threshold)
            reference_score: Reference score for binary/categorical scores
            (defaults to self.reference_score)
            threshold_operator: Comparison operator (defaults based on score_type)

        Returns:
            bool: True if the score meets the success criteria
        """
        # Use default values from instance if not provided
        if threshold is None:
            threshold = self.threshold
        if reference_score is None:
            reference_score = self.reference_score

        # Delegate to the score evaluator's comprehensive implementation
        return self._score_evaluator.evaluate_score(
            score=score,
            threshold=threshold,
            threshold_operator=threshold_operator,
            reference_score=reference_score,
            score_type=score_type,
        )
