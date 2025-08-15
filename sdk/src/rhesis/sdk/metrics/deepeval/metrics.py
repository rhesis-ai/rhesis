from typing import Any, Dict, List, Optional

from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
    FaithfulnessMetric,
)

from rhesis.backend.metrics.base import MetricResult, retry_evaluation
from rhesis.backend.metrics.deepeval.metric_base import DeepEvalMetricBase


class DeepEvalAnswerRelevancy(DeepEvalMetricBase):
    """DeepEval implementation of Answer Relevancy metric."""

    def __init__(self, threshold: float = 0.5, model_config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="Answer Relevancy",
            threshold=threshold,
            metric_type="rag",
            model_config=model_config,
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

    def __init__(self, threshold: float = 0.5, model_config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="Faithfulness", threshold=threshold, metric_type="rag", model_config=model_config
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

    def __init__(self, threshold: float = 0.5, model_config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="Contextual Relevancy",
            threshold=threshold,
            metric_type="rag",
            model_config=model_config,
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

    def __init__(self, threshold: float = 0.5, model_config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="Contextual Precision",
            threshold=threshold,
            metric_type="rag",
            model_config=model_config,
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
        return False


class DeepEvalContextualRecall(DeepEvalMetricBase):
    """DeepEval implementation of Contextual Recall metric."""

    def __init__(self, threshold: float = 0.5, model_config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="Contextual Recall",
            threshold=threshold,
            metric_type="rag",
            model_config=model_config,
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
