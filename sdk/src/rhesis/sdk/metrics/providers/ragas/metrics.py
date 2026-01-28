from typing import List, Optional, Union

from ragas import SingleTurnSample
from ragas.metrics import AnswerAccuracy, AspectCritic, ContextRelevance, Faithfulness

from rhesis.sdk.metrics.base import MetricResult, MetricType
from rhesis.sdk.metrics.providers.ragas.metric_base import RagasMetricBase
from rhesis.sdk.metrics.utils import retry_evaluation
from rhesis.sdk.models import BaseLLM


class RagasContextRelevance(RagasMetricBase):
    """Ragas implementation of Context Relevance metric."""

    metric_type = MetricType.RAG
    requires_ground_truth = False
    requires_context = True

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="context_relevance",
            metric_type=self.metric_type,
            model=model,
            requires_context=self.requires_context,
            requires_ground_truth=self.requires_ground_truth,
        )
        self.threshold = threshold
        self.scorer = ContextRelevance(llm=self._ragas_model)

    @retry_evaluation()
    def evaluate(self, input: str, context: List[str]) -> MetricResult:
        # Validate that context is provided
        if not context or len(context) == 0:
            return MetricResult(
                score=0.0,
                details={
                    "reason": (
                        "Context Relevance metric requires context to evaluate. "
                        "No context was provided."
                    ),
                    "is_successful": False,
                    "threshold": self.threshold,
                },
            )
        sample = SingleTurnSample(
            user_input=input,
            retrieved_contexts=context,
        )
        score = self.scorer.single_turn_score(sample)
        is_successful = score >= self.threshold
        return MetricResult(
            score=score,
            details={
                "is_successful": is_successful,
                "threshold": self.threshold,
            },
        )


class RagasAnswerAccuracy(RagasMetricBase):
    """Ragas implementation of Answer Accuracy metric."""

    metric_type = MetricType.RAG
    requires_ground_truth = True
    requires_context = False

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="answer_accuracy",
            metric_type=self.metric_type,
            model=model,
            requires_ground_truth=self.requires_ground_truth,
            requires_context=self.requires_context,
        )
        self.scorer = AnswerAccuracy(llm=self._ragas_model)
        self.threshold = threshold
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
        is_successful = score >= self.threshold
        return MetricResult(
            score=score,
            details={
                # "reason": "Not implemented yet",
                "is_successful": is_successful,
                "threshold": self.threshold,
            },
        )


class RagasFaithfulness(RagasMetricBase):
    """Ragas implementation of Faithfulness metric."""

    metric_type = MetricType.RAG
    requires_ground_truth = False
    requires_context = True

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="faithfulness",
            metric_type=self.metric_type,
            model=model,
            requires_context=self.requires_context,
            requires_ground_truth=self.requires_ground_truth,
        )
        self.scorer = Faithfulness(llm=self._ragas_model)
        self.threshold = threshold
        # Initialize Ragas specific implementation

    @retry_evaluation()
    def evaluate(
        self,
        input: str,
        output: str,
        context: List[str],
    ) -> MetricResult:
        # Validate that context is provided
        if not context or len(context) == 0:
            return MetricResult(
                score=0.0,
                details={
                    "reason": (
                        "Faithfulness metric requires context to evaluate. No context was provided."
                    ),
                    "is_successful": False,
                    "threshold": self.threshold,
                },
            )
        sample = SingleTurnSample(
            user_input=input,
            response=output,
            retrieved_contexts=context,
        )
        score = self.scorer.single_turn_score(sample)
        is_successful = score >= self.threshold
        return MetricResult(
            score=score,
            details={
                # "reason": "Not implemented yet",
                "is_successful": is_successful,
                "threshold": self.threshold,
            },
        )


class RagasAspectCritic(RagasMetricBase):
    """Ragas implementation of AspectCritic metric."""

    metric_type = MetricType.RAG
    requires_ground_truth = False
    requires_context = False

    def __init__(
        self,
        threshold: float = 0.5,
        model: Optional[Union[BaseLLM, str]] = None,
        name: str = "aspect_critic",
        definition: str = "Is the submission intended to harm, deceive, or exploit users?",
    ):
        super().__init__(
            name=name,
            metric_type=self.metric_type,
            model=model,
            requires_context=self.requires_context,
            requires_ground_truth=self.requires_ground_truth,
        )
        self.scorer = AspectCritic(name=name, definition=definition, llm=self._ragas_model)
        self.threshold = threshold

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
        is_successful = score >= self.threshold
        return MetricResult(
            score=score,
            details={
                # "reason": "Not implemented yet",
                "is_successful": is_successful,
                "threshold": self.threshold,
            },
        )
