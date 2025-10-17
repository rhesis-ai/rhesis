from typing import List, Optional, Union

from deepeval.metrics import (
    AnswerRelevancyMetric,
    BiasMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
    FaithfulnessMetric,
)

from rhesis.sdk.metrics.base import MetricResult, MetricType
from rhesis.sdk.metrics.providers.deepeval.metric_base import DeepEvalMetricBase
from rhesis.sdk.metrics.utils import retry_evaluation
from rhesis.sdk.models.base import BaseLLM


class DeepEvalAnswerRelevancy(DeepEvalMetricBase):
    """DeepEval implementation of Answer Relevancy metric."""

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="Answer Relevancy",
            threshold=threshold,
            metric_type=MetricType.RAG,
            model=model,
        )
        self._metric = AnswerRelevancyMetric(threshold=threshold, model=self.model)

    @retry_evaluation()
    def evaluate(
        self, input: str, output: str, expected_output: Optional[str], context: List[str]
    ) -> MetricResult:
        test_case = self._create_test_case(input, output, expected_output, context)
        self._metric.measure(test_case)
        return MetricResult(
            score=self._metric.score,
            details={
                "reason": self._metric.reason,
                "is_successful": self._metric.is_successful(),
                "threshold": self._threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return True


class DeepEvalFaithfulness(DeepEvalMetricBase):
    """DeepEval implementation of Faithfulness metric."""

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="Faithfulness", threshold=threshold, metric_type=MetricType.RAG, model=model
        )
        self._metric = FaithfulnessMetric(threshold=threshold, model=self.model)

    @retry_evaluation()
    def evaluate(
        self, input: str, output: str, expected_output: Optional[str], context: List[str]
    ) -> MetricResult:
        test_case = self._create_test_case(input, output, expected_output, context)
        self._metric.measure(test_case)
        return MetricResult(
            score=self._metric.score,
            details={
                "reason": self._metric.reason,
                "is_successful": self._metric.is_successful(),
                "threshold": self._threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return False


class DeepEvalContextualRelevancy(DeepEvalMetricBase):
    """DeepEval implementation of Contextual Relevancy metric."""

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="Contextual Relevancy",
            threshold=threshold,
            metric_type=MetricType.RAG,
            model=model,
        )
        self._metric = ContextualRelevancyMetric(threshold=threshold, model=self.model)

    @retry_evaluation()
    def evaluate(
        self, input: str, output: str, expected_output: Optional[str], context: List[str]
    ) -> MetricResult:
        test_case = self._create_test_case(input, output, expected_output, context)
        self._metric.measure(test_case)
        return MetricResult(
            score=self._metric.score,
            details={
                "reason": self._metric.reason,
                "is_successful": self._metric.is_successful(),
                "threshold": self._threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return False


class DeepEvalContextualPrecision(DeepEvalMetricBase):
    """DeepEval implementation of Contextual Precision metric."""

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="Contextual Precision",
            threshold=threshold,
            metric_type=MetricType.RAG,
            model=model,
        )
        self._metric = ContextualPrecisionMetric(threshold=threshold, model=self.model)

    @retry_evaluation()
    def evaluate(
        self, input: str, output: str, expected_output: Optional[str], context: List[str]
    ) -> MetricResult:
        test_case = self._create_test_case(input, output, expected_output, context)
        self._metric.measure(test_case)
        return MetricResult(
            score=self._metric.score,
            details={
                "reason": self._metric.reason,
                "is_successful": self._metric.is_successful(),
                "threshold": self._threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return True


class DeepEvalContextualRecall(DeepEvalMetricBase):
    """DeepEval implementation of Contextual Recall metric."""

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="Contextual Recall",
            threshold=threshold,
            metric_type=MetricType.RAG,
            model=model,
        )
        self._metric = ContextualRecallMetric(threshold=threshold, model=self.model)

    @retry_evaluation()
    def evaluate(
        self, input: str, output: str, expected_output: Optional[str], context: List[str]
    ) -> MetricResult:
        test_case = self._create_test_case(input, output, expected_output, context)
        self._metric.measure(test_case)
        return MetricResult(
            score=self._metric.score,
            details={
                "reason": self._metric.reason,
                "is_successful": self._metric.is_successful(),
                "threshold": self._threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return False


class DeepEvalBias(DeepEvalMetricBase):
    """DeepEval implementation of Bias metric."""

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="Bias",
            threshold=threshold,
            metric_type=MetricType.GENERATION,
            model=model,
        )
        self._metric = BiasMetric(threshold=threshold, model=self.model)

    @retry_evaluation()
    def evaluate(
        self, input: str, output: str, expected_output: Optional[str], context: List[str]
    ) -> MetricResult:
        test_case = self._create_test_case(input, output, expected_output, context)
        self._metric.measure(test_case)
        return MetricResult(
            score=self._metric.score,
            details={
                "reason": self._metric.reason,
                "is_successful": self._metric.is_successful(),
                "threshold": self._threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return False
