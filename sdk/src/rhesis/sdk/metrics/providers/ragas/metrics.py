from typing import List, Optional, Union

from ragas import SingleTurnSample
from ragas.metrics import AnswerAccuracy, AspectCritic, ContextRelevance, Faithfulness

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
    def evaluate(self, input: str, context: List[str]) -> MetricResult:
        sample = SingleTurnSample(
            user_input=input,
            retrieved_contexts=context,
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


class RagasFaithfulness(RagasMetricBase):
    """Ragas implementation of Faithfulness metric."""

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="faithfulness", threshold=threshold, metric_type=MetricType.RAG, model=model
        )
        self.scorer = Faithfulness(llm=self.model)
        # Initialize Ragas specific implementation

    @retry_evaluation()
    def evaluate(
        self,
        input: str,
        output: str,
        context: List[str],
    ) -> MetricResult:
        sample = SingleTurnSample(
            user_input=input,
            response=output,
            retrieved_contexts=context,
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
        return False


class RagasAspectCritic(RagasMetricBase):
    """Ragas implementation of AspectCritic metric."""

    def __init__(
        self,
        threshold: float = 0.5,
        model: Optional[Union[BaseLLM, str]] = None,
        name: str = "aspect_critic",
        definition: str = "Is the submission intended to harm, deceive, or exploit users?",
    ):
        super().__init__(name=name, threshold=threshold, metric_type=MetricType.RAG, model=model)
        self.scorer = AspectCritic(name=name, definition=definition, llm=self.model)
        # Initialize Ragas specific implementation

    @retry_evaluation()
    def evaluate(
        self,
        input: str,
        output: str,
    ) -> MetricResult:
        sample = SingleTurnSample(
            user_input=input,
            response=output,
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
        return False
