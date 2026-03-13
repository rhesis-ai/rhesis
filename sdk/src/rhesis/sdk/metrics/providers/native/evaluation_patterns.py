"""Reusable evaluation patterns for metrics.

This module provides common evaluation patterns to reduce code duplication
across different judge types (single-turn and conversational).
"""

from typing import Any, Dict, Optional, Type

from pydantic import BaseModel

from rhesis.sdk.async_utils import run_sync
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
    - model: Language model instance
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
        return run_sync(
            self._a_execute_numeric_evaluation(
                prompt=prompt,
                response_schema=response_schema,
                additional_details=additional_details,
            )
        )

    async def _a_execute_numeric_evaluation(
        self,
        prompt: str,
        response_schema: Type[BaseModel],
        additional_details: Optional[Dict[str, Any]] = None,
    ) -> MetricResult:
        """Async version of _execute_numeric_evaluation."""
        details = self._get_base_details(prompt)

        threshold_operator_value = (
            (
                self.threshold_operator.value
                if isinstance(self.threshold_operator, ThresholdOperator)
                else str(self.threshold_operator)
            )
            if self.threshold_operator
            else None
        )

        details.update(
            {
                "threshold_operator": threshold_operator_value,
                "min_score": self.min_score,
                "max_score": self.max_score,
                "threshold": self.threshold,
            }
        )

        if additional_details:
            details.update(additional_details)

        try:
            response = await self.model.a_generate(prompt, schema=response_schema)
            response = response_schema(**response)  # type: ignore[arg-type]

            if not hasattr(response, "score"):
                raise ValueError(
                    f"Response schema {response_schema.__name__} must have 'score' field"
                )
            if not hasattr(response, "reason"):
                raise ValueError(
                    f"Response schema {response_schema.__name__} must have 'reason' field"
                )

            score = response.score
            reason = response.reason
            is_successful = self._evaluate_score(score=score)

            details.update(
                {
                    "score": score,
                    "reason": reason,
                    "is_successful": is_successful,
                }
            )

            response_dict = response.model_dump(exclude={"score", "reason"})
            details.update(response_dict)

            return MetricResult(score=score, details=details)

        except Exception as e:
            return self._handle_evaluation_error(e, details, 0.0)
