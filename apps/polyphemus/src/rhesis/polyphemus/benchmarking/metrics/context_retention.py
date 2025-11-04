"""
Context Retention metric for evaluating correct usage of provided context.
"""

from typing import Optional, Union

from rhesis.sdk.metrics import NumericJudge
from rhesis.sdk.models import BaseLLM


class ContextRetentionJudge(NumericJudge):
    """
    Evaluates whether the model correctly used the provided context.

    This metric assesses how well the output incorporates and respects
    information from the provided context (system prompt or additional context).

    Inherits from NumericJudge with prepopulated evaluation criteria.
    """

    def __init__(
        self,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        threshold: Optional[float] = None,
        model: Optional[Union[str, BaseLLM]] = None,
        **kwargs,
    ):
        """
        Initialize the ContextRetentionJudge metric.

        Args:
            min_score: Minimum possible score (defaults to 0)
            max_score: Maximum possible score (defaults to 1)
            threshold: Success threshold (defaults to midpoint)
            model: The LLM model to use for evaluation
            **kwargs: Additional keyword arguments passed to NumericJudge
        """
        super().__init__(
            name="context_retention",
            evaluation_prompt="Did the model use the provided context correctly?",
            evaluation_steps="1. Read context\n2. Read response\n3. Check usage",
            min_score=min_score,
            max_score=max_score,
            threshold=threshold,
            model=model,
            **kwargs,
        )
