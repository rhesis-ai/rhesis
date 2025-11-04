"""
Relevancy metric for evaluating whether LLM outputs address the input question.
Uses DeepEval's AnswerRelevancy metric from the SDK.
"""

from typing import Optional, Union

from rhesis.sdk.metrics.providers.deepeval import DeepEvalAnswerRelevancy
from rhesis.sdk.models import BaseLLM


class RelevancyJudge(DeepEvalAnswerRelevancy):
    """
    Evaluates whether the response appropriately answers the input question.

    This metric assesses how well the output addresses the question or prompt,
    checking if the key points are covered and if the response stays on topic.

    Wraps DeepEval's AnswerRelevancy metric for consistency with the benchmarking framework.
    """

    def __init__(
        self,
        threshold: Optional[float] = 0.5,
        model: Optional[Union[str, BaseLLM]] = None,
    ):
        """
        Initialize the RelevancyJudge metric.

        Args:
            threshold: Success threshold (defaults to 0.5)
            model: The LLM model to use for evaluation
            **kwargs: Additional keyword arguments passed to DeepEvalAnswerRelevancy
        """
        super().__init__(
            threshold=threshold,
            model=model,
        )
