"""Reusable evaluation patterns for metrics.

This module provides common evaluation patterns to reduce code duplication
across different judge types (single-turn and conversational).
"""

from typing import Any, Dict, Optional, Type

from pydantic import BaseModel

from rhesis.sdk.metrics.base import MetricResult
from rhesis.sdk.metrics.constants import ThresholdOperator


class NumericEvaluationMixin:
    """
    Mixin providing reusable numeric evaluation pattern.

    This mixin provides the common workflow used by numeric judges:
    1. Build details dictionary with threshold info
    2. Generate LLM response with structured output
    3. Evaluate score against threshold
    4. Return result or handle errors

    This pattern is shared by:
    - NumericJudge (single-turn)
    - GoalAchievementJudge (conversational)
    - Any future numeric judges

    Expected attributes on the class using this mixin:
    - model: LLM model instance
    - min_score: Minimum score value
    - max_score: Maximum score value
    - threshold: Success threshold
    - threshold_operator: Comparison operator
    - _get_base_details(prompt): Method to get base details
    - _evaluate_score(score): Method to evaluate score against threshold
    - _handle_evaluation_error(e, details, default): Method to handle errors
    """

    def _execute_numeric_evaluation(
        self,
        prompt: str,
        response_schema: Type[BaseModel],
        additional_details: Optional[Dict[str, Any]] = None,
    ) -> MetricResult:
        """
        Execute standard numeric evaluation workflow.

        This method encapsulates the common pattern used by all numeric judges:
        1. Build details dict with threshold information
        2. Call LLM with structured output schema
        3. Extract score and reason from response
        4. Evaluate score against threshold
        5. Return result with all details, or error result

        Args:
            prompt: The evaluation prompt to send to the LLM
            response_schema: Pydantic model for structured LLM response
                            (must have 'score' and 'reason' fields)
            additional_details: Optional dict of additional details to include
                               (e.g., turn_count, goal for conversational metrics)

        Returns:
            MetricResult with score and comprehensive details

        Note:
            The response_schema must be a Pydantic BaseModel with at minimum:
            - score: float field
            - reason: str field
        """
        # Get base details (prompt, score_type, etc.)
        details = self._get_base_details(prompt)

        # Get threshold operator value (handle both enum and string)
        threshold_operator_value = (
            (
                self.threshold_operator.value
                if isinstance(self.threshold_operator, ThresholdOperator)
                else str(self.threshold_operator)
            )
            if self.threshold_operator
            else None
        )

        # Add threshold-related fields
        details.update(
            {
                "threshold_operator": threshold_operator_value,
                "min_score": self.min_score,
                "max_score": self.max_score,
                "threshold": self.threshold,
            }
        )

        # Add any additional mode-specific details
        if additional_details:
            details.update(additional_details)

        try:
            # Generate LLM response with structured output
            response = self.model.generate(prompt, schema=response_schema)
            response = response_schema(**response)  # type: ignore

            # Extract score and reason
            score = response.score
            reason = response.reason

            # Evaluate score against threshold
            is_successful = self._evaluate_score(score=score)

            # Update details with evaluation results
            details.update(
                {
                    "score": score,
                    "reason": reason,
                    "is_successful": is_successful,
                }
            )

            return MetricResult(score=score, details=details)

        except Exception as e:
            # Handle errors with standard error handling
            return self._handle_evaluation_error(e, details, 0.0)

