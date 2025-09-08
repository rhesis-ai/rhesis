import logging
from typing import Optional, Union

from rhesis.sdk.metrics.constants import (
    OPERATOR_MAP,
    VALID_OPERATORS_BY_SCORE_TYPE,
    ScoreType,
    ThresholdOperator,
)

# Set up logger for the SDK
logger = logging.getLogger(__name__)


class ScoreEvaluator:
    """Class responsible for evaluating scores against thresholds and criteria."""

    @staticmethod
    def _sanitize_threshold_operator(
        threshold_operator: Union[ThresholdOperator, str, None],
    ) -> Optional[ThresholdOperator]:
        """
        Sanitize and validate the threshold operator.

        Args:
            threshold_operator: The threshold operator to sanitize

        Returns:
            ThresholdOperator: Sanitized and validated threshold operator, or None if invalid

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
                logger.warning(
                    f"Invalid threshold operator: '{threshold_operator}'. "
                    f"Valid operators are: {', '.join([op.value for op in ThresholdOperator])}"
                )
                return None

        # Validate that it's a valid ThresholdOperator
        if not isinstance(threshold_operator, ThresholdOperator):
            logger.warning(
                f"threshold_operator must be a ThresholdOperator enum or valid string, "
                f"got {type(threshold_operator)}"
            )
            return None

        return threshold_operator

    @staticmethod
    def _validate_operator_for_score_type(
        threshold_operator: ThresholdOperator, score_type: ScoreType
    ) -> bool:
        """
        Validate that the threshold operator is appropriate for the score type.

        Args:
            threshold_operator: The threshold operator to validate
            score_type: The score type to validate against

        Returns:
            bool: True if the operator is valid for the score type
        """
        valid_operators = VALID_OPERATORS_BY_SCORE_TYPE.get(score_type, set())
        if threshold_operator not in valid_operators:
            valid_ops_str = ", ".join([op.value for op in valid_operators])
            logger.warning(
                (
                    f"Operator '{threshold_operator.value}' is not valid for score type "
                    f"'{score_type.value}'. Valid operators for {score_type.value} are: "
                    f"{valid_ops_str}"
                )
            )
            return False
        return True

    @staticmethod
    def _determine_score_type(
        score: Union[float, str, int], threshold_operator: Optional[str]
    ) -> ScoreType:
        """
        Determine the score type based on the score value and threshold operator.

        Args:
            score: The score value
            threshold_operator: The threshold operator

        Returns:
            ScoreType: The determined score type
        """
        # If it's a string score, determine if it's binary or categorical
        if isinstance(score, str):
            # Common binary values
            binary_values = {
                "true",
                "false",
                "yes",
                "no",
                "pass",
                "fail",
                "success",
                "failure",
                "1",
                "0",
            }
            if score.lower().strip() in binary_values:
                return ScoreType.BINARY
            else:
                return ScoreType.CATEGORICAL

        # If it's numeric, it's numeric type
        return ScoreType.NUMERIC

    def evaluate_score(
        self,
        score: Union[float, str, int],
        threshold: Optional[float],
        threshold_operator: Optional[str],
        reference_score: Optional[str] = None,
        score_type: Optional[Union[ScoreType, str]] = None,
    ) -> bool:
        """
        Evaluate whether a metric score meets the success criteria based on threshold and operator.
        This method incorporates all the functionality from metric_base.py for comprehensive
        score evaluation.

        Args:
            score: The metric score (can be numeric or string)
            threshold: The threshold value for numeric scores
            threshold_operator: The comparison operator ('<', '>', '>=', '<=', '=', '!=')
            reference_score: Reference score for binary/categorical metrics
            score_type: Explicit score type, if not provided will be auto-determined

        Returns:
            bool: True if the metric score meets the success criteria
        """
        # Determine score type if not provided
        if score_type is None:
            score_type = self._determine_score_type(score, threshold_operator)
        elif isinstance(score_type, str):
            try:
                score_type = ScoreType(score_type)
            except ValueError:
                logger.warning(f"Invalid score type '{score_type}', auto-determining from score")
                score_type = self._determine_score_type(score, threshold_operator)

        # Sanitize and validate threshold operator
        sanitized_operator = self._sanitize_threshold_operator(threshold_operator)

        # Set default threshold operator based on score type if none provided or invalid
        if sanitized_operator is None:
            if score_type == ScoreType.NUMERIC:
                sanitized_operator = ThresholdOperator.GREATER_THAN_OR_EQUAL
            else:  # BINARY or CATEGORICAL
                sanitized_operator = ThresholdOperator.EQUAL
            logger.debug(
                f"Using default operator '{sanitized_operator.value}'"
                f"for score type '{score_type.value}'"
            )

        # Validate operator for score type
        if not self._validate_operator_for_score_type(sanitized_operator, score_type):
            # Fall back to appropriate default if validation fails
            if score_type == ScoreType.NUMERIC:
                sanitized_operator = ThresholdOperator.GREATER_THAN_OR_EQUAL
            else:
                sanitized_operator = ThresholdOperator.EQUAL
            logger.debug(
                f"Falling back to operator '{sanitized_operator.value}'"
                f"for score type '{score_type.value}'"
            )

        # Handle different score types
        if score_type == ScoreType.NUMERIC:
            return self._evaluate_numeric_score(score, threshold, sanitized_operator)
        else:  # BINARY or CATEGORICAL
            return self._evaluate_categorical_score(
                score, reference_score, threshold, sanitized_operator, score_type
            )

    def _evaluate_numeric_score(
        self,
        score: Union[float, int],
        threshold: Optional[float],
        threshold_operator: ThresholdOperator,
    ) -> bool:
        """
        Evaluate numeric scores against threshold using the specified operator.

        Args:
            score: The numeric score
            threshold: The threshold value
            threshold_operator: The comparison operator

        Returns:
            bool: True if the score meets the criteria
        """
        # Convert score to float if it's not already
        try:
            numeric_score = float(score)
        except (ValueError, TypeError):
            logger.warning(f"Could not convert score '{score}' to numeric value")
            return False

        # Validate threshold is provided for numeric scores
        if threshold is None:
            raise ValueError("Threshold is required for numeric score type")

        # Use operator module for comparison
        op_func = OPERATOR_MAP.get(threshold_operator)
        if op_func is None:
            # Fallback to default behavior
            logger.warning(f"Unknown operator '{threshold_operator}', defaulting to '>='")
            return numeric_score >= threshold

        return op_func(numeric_score, threshold)

    def _evaluate_categorical_score(
        self,
        score: Union[str, float, int],
        reference_score: Optional[str],
        threshold: Optional[float],
        threshold_operator: ThresholdOperator,
        score_type: ScoreType,
    ) -> bool:
        """
        Evaluate binary/categorical scores against reference score using the specified operator.

        Args:
            score: The score value
            reference_score: The reference score to compare against
            threshold: The threshold (used as reference if reference_score not provided)
            threshold_operator: The comparison operator
            score_type: The score type (BINARY or CATEGORICAL)

        Returns:
            bool: True if the score meets the criteria
        """
        # Determine reference value
        if reference_score is None:
            if threshold is not None:
                reference_value = str(threshold)
            else:
                # Use the actual score type to determine the error message
                score_type_name = score_type.value.lower()
                raise ValueError(f"Reference score is required for {score_type_name} score type")
        else:
            reference_value = reference_score

        # Convert score to string for comparison
        score_str = (
            str(score).lower().strip() if not isinstance(score, str) else score.lower().strip()
        )
        reference_str = reference_value.lower().strip()

        # Use operator module for comparison
        op_func = OPERATOR_MAP.get(threshold_operator)
        if op_func is None:
            # Fallback to equality check
            logger.warning(f"Unknown operator '{threshold_operator}', defaulting to equality")
            return score_str == reference_str

        return op_func(score_str, reference_str)
