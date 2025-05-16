from typing import List, Optional

from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
    FaithfulnessMetric,
)
from deepeval.test_case import LLMTestCase

from .base import BaseMetric, BaseMetricFactory, MetricResult, MetricType


class DeepEvalMetricBase(BaseMetric):
    """Base class for DeepEval metrics with common functionality."""

    def __init__(self, name: str, threshold: float = 0.5, metric_type: MetricType = "rag"):
        super().__init__(name=name, metric_type=metric_type)
        self._threshold = threshold
        self._metric = None  # Will be set by child classes

    @property
    def threshold(self) -> float:
        return self._threshold

    @threshold.setter
    def threshold(self, value: float):
        if not 0 <= value <= 1:
            raise ValueError("Threshold must be between 0 and 1")
        self._threshold = value
        if self._metric:
            self._metric.threshold = value

    @property
    def is_successful(self) -> bool:
        """Check if the metric passed the threshold."""
        return self._metric.is_successful() if self._metric else False

    @property
    def strict_mode(self) -> bool:
        return self._metric.strict_mode if self._metric else False

    @strict_mode.setter
    def strict_mode(self, value: bool):
        if self._metric:
            self._metric.strict_mode = value

    @property
    def verbose_mode(self) -> bool:
        return self._metric.verbose_mode if self._metric else False

    @verbose_mode.setter
    def verbose_mode(self, value: bool):
        if self._metric:
            self._metric.verbose_mode = value

    def _create_test_case(
        self, input: str, output: str, expected_output: str, context: List[str]
    ) -> LLMTestCase:
        """Create a DeepEval test case from input parameters."""
        return LLMTestCase(
            input=input,
            actual_output=output,
            expected_output=expected_output,
            retrieval_context=context,
        )


class DeepEvalAnswerRelevancy(DeepEvalMetricBase):
    """DeepEval implementation of Answer Relevancy metric."""

    def __init__(self, threshold: float = 0.5):
        super().__init__(name="answer_relevancy", threshold=threshold, metric_type="rag")
        self._metric = AnswerRelevancyMetric(threshold=threshold)

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


class DeepEvalFaithfulness(DeepEvalMetricBase):
    """DeepEval implementation of Faithfulness metric."""

    def __init__(self, threshold: float = 0.5):
        super().__init__(name="faithfulness", threshold=threshold, metric_type="rag")
        self._metric = FaithfulnessMetric(threshold=threshold)

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

    def __init__(self, threshold: float = 0.5):
        super().__init__(name="contextual_relevancy", threshold=threshold, metric_type="rag")
        self._metric = ContextualRelevancyMetric(threshold=threshold)

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

    def __init__(self, threshold: float = 0.5):
        super().__init__(name="contextual_precision", threshold=threshold, metric_type="rag")
        self._metric = ContextualPrecisionMetric(threshold=threshold)

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


class DeepEvalContextualRecall(DeepEvalMetricBase):
    """DeepEval implementation of Contextual Recall metric."""

    def __init__(self, threshold: float = 0.5):
        super().__init__(name="contextual_recall", threshold=threshold, metric_type="rag")
        self._metric = ContextualRecallMetric(threshold=threshold)

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


class DeepEvalMetricFactory(BaseMetricFactory):
    """Factory for creating DeepEval metric instances."""

    _metrics = {
        "answer_relevancy": DeepEvalAnswerRelevancy,
        "faithfulness": DeepEvalFaithfulness,
        "contextual_relevancy": DeepEvalContextualRelevancy,
        "contextual_precision": DeepEvalContextualPrecision,
        "contextual_recall": DeepEvalContextualRecall,
    }

    def create(self, metric_name: str, **kwargs) -> BaseMetric:
        if metric_name not in self._metrics:
            available_metrics = list(self._metrics.keys())
            raise ValueError(
                f"Unknown metric name: {metric_name}. Available metrics: {available_metrics}"
            )
        return self._metrics[metric_name](**kwargs)

    def list_supported_metrics(self) -> List[str]:
        return list(self._metrics.keys())
