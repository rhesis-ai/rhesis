from typing import List, Optional, Union

from ragas import SingleTurnSample
from ragas.metrics import AnswerAccuracy, ContextRelevance

from rhesis.sdk.metrics.base import MetricResult, MetricType
from rhesis.sdk.metrics.providers.ragas.metric_base import RagasMetricBase
from rhesis.sdk.metrics.utils import retry_evaluation
from rhesis.sdk.models import BaseLLM


class RagasContextRelevance(RagasMetricBase):
    """Ragas implementation of Context Relevance metric."""

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="context_relevance", threshold=threshold, metric_type=MetricType.RAG, model=model
        )
        self.scorer = ContextRelevance(llm=self.model)
        # Initialize Ragas specific implementation

    @retry_evaluation()
    def evaluate(
        self,
        input: str,
        output: str,
        expected_output: Optional[str] = None,
        context: Optional[List[str]] = None,
    ) -> MetricResult:
        sample = SingleTurnSample(
            user_input=input,
            response=output,
            reference=expected_output,
        )
        score = self.scorer.single_turn_score(sample)
        is_successful = score >= self._threshold
        return MetricResult(
            score=score,
            details={
                # "reason": "Not implemented yet",
                "is_successful": is_successful,
                "threshold": self._threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return True


class RagasAnswerAccuracy(RagasMetricBase):
    """Ragas implementation of Answer Accuracy metric."""

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="answer_accuracy", threshold=threshold, metric_type=MetricType.RAG, model=model
        )
        self.scorer = AnswerAccuracy(llm=self.model)
        # Initialize Ragas specific implementation

    @retry_evaluation()
    def evaluate(
        self,
        input: str,
        output: str,
        expected_output: Optional[str] = None,
        context: Optional[List[str]] = None,
    ) -> MetricResult:
        sample = SingleTurnSample(
            user_input=input,
            response=output,
            reference=expected_output,
        )
        score = self.scorer.single_turn_score(sample)
        is_successful = score >= self._threshold
        return MetricResult(
            score=score,
            details={
                # "reason": "Not implemented yet",
                "is_successful": is_successful,
                "threshold": self._threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return True
