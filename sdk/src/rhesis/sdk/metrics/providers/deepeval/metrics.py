from typing import List, Optional, Union

from deepeval.metrics import (
    AnswerRelevancyMetric,  # type: ignore
    BiasMetric,  # type: ignore
    ContextualPrecisionMetric,  # type: ignore
    ContextualRecallMetric,  # type: ignore
    ContextualRelevancyMetric,  # type: ignore
    FaithfulnessMetric,  # type: ignore
    MisuseMetric,  # type: ignore
    NonAdviceMetric,  # type: ignore
    PIILeakageMetric,  # type: ignore
    RoleViolationMetric,  # type: ignore
    ToxicityMetric,  # type: ignore
)

from rhesis.sdk.metrics.base import MetricResult, MetricType
from rhesis.sdk.metrics.providers.deepeval.metric_base import DeepEvalMetricBase
from rhesis.sdk.metrics.utils import retry_evaluation
from rhesis.sdk.models.base import BaseLLM


class DeepEvalAnswerRelevancy(DeepEvalMetricBase):
    """DeepEval implementation of Answer Relevancy metric."""

    metric_type = MetricType.RAG

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="Answer Relevancy",
            metric_type=self.metric_type,
            model=model,
        )
        self._metric = AnswerRelevancyMetric(threshold=threshold, model=self._deepeval_model)
        self.threshold = threshold

    @retry_evaluation()
    def evaluate(
        self,
        input: str,
        output: str,
    ) -> MetricResult:
        test_case = self._create_test_case(input, output)
        self._metric.measure(test_case)
        return MetricResult(
            score=self._metric.score,
            details={
                "reason": self._metric.reason,
                "is_successful": self._metric.is_successful(),
                "threshold": self.threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return False


class DeepEvalFaithfulness(DeepEvalMetricBase):
    """DeepEval implementation of Faithfulness metric."""

    metric_type = MetricType.RAG

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(name="Faithfulness", metric_type=self.metric_type, model=model)
        self._metric = FaithfulnessMetric(threshold=threshold, model=self._deepeval_model)
        self.threshold = threshold

    @retry_evaluation()
    def evaluate(
        self,
        input: str,
        output: str,
        context: Optional[List[str]] = None,
    ) -> MetricResult:
        test_case = self._create_test_case(input, output, context=context)
        self._metric.measure(test_case)
        return MetricResult(
            score=self._metric.score,
            details={
                "reason": self._metric.reason,
                "is_successful": self._metric.is_successful(),
                "threshold": self.threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return False


class DeepEvalContextualRelevancy(DeepEvalMetricBase):
    """DeepEval implementation of Contextual Relevancy metric."""

    metric_type = MetricType.RAG

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="Contextual Relevancy",
            metric_type=self.metric_type,
            model=model,
        )
        self._metric = ContextualRelevancyMetric(threshold=threshold, model=self._deepeval_model)
        self.threshold = threshold

    @retry_evaluation()
    def evaluate(
        self,
        input: str,
        context: Optional[List[str]] = None,
    ) -> MetricResult:
        test_case = self._create_test_case(input=input, context=context)
        self._metric.measure(test_case)
        return MetricResult(
            score=self._metric.score,
            details={
                "reason": self._metric.reason,
                "is_successful": self._metric.is_successful(),
                "threshold": self.threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return False


class DeepEvalContextualPrecision(DeepEvalMetricBase):
    """DeepEval implementation of Contextual Precision metric."""

    metric_type = MetricType.RAG

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="Contextual Precision",
            metric_type=self.metric_type,
            model=model,
        )
        self._metric = ContextualPrecisionMetric(threshold=threshold, model=self._deepeval_model)
        self.threshold = threshold

    @retry_evaluation()
    def evaluate(
        self,
        input: str,
        output: str,
        expected_output: Optional[str] = None,
        context: Optional[List[str]] = None,
    ) -> MetricResult:
        test_case = self._create_test_case(input, output, expected_output, context)
        self._metric.measure(test_case)
        return MetricResult(
            score=self._metric.score,
            details={
                "reason": self._metric.reason,
                "is_successful": self._metric.is_successful(),
                "threshold": self.threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return True


class DeepEvalContextualRecall(DeepEvalMetricBase):
    """DeepEval implementation of Contextual Recall metric."""

    metric_type = MetricType.RAG

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="Contextual Recall",
            metric_type=self.metric_type,
            model=model,
        )
        self._metric = ContextualRecallMetric(threshold=threshold, model=self._deepeval_model)
        self.threshold = threshold

    @retry_evaluation()
    def evaluate(
        self,
        input: str,
        output: str,
        expected_output: Optional[str] = None,
        context: Optional[List[str]] = None,
    ) -> MetricResult:
        test_case = self._create_test_case(input, output, expected_output, context)
        self._metric.measure(test_case)
        return MetricResult(
            score=self._metric.score,
            details={
                "reason": self._metric.reason,
                "is_successful": self._metric.is_successful(),
                "threshold": self.threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return False


class DeepEvalBias(DeepEvalMetricBase):
    """DeepEval implementation of Bias metric."""

    metric_type = MetricType.GENERATION

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="Bias",
            metric_type=self.metric_type,
            model=model,
        )
        self._metric = BiasMetric(threshold=threshold, model=self._deepeval_model)
        self.threshold = threshold

    @retry_evaluation()
    def evaluate(
        self,
        input: str,
        output: str,
    ) -> MetricResult:
        test_case = self._create_test_case(input, output)
        self._metric.measure(test_case)
        return MetricResult(
            score=self._metric.score,
            details={
                "reason": self._metric.reason,
                "is_successful": self._metric.is_successful(),
                "threshold": self.threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return False


class DeepEvalToxicity(DeepEvalMetricBase):
    """DeepEval implementation of Toxicity metric."""

    metric_type = MetricType.CLASSIFICATION

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="Toxicity",
            metric_type=self.metric_type,
            model=model,
        )
        self._metric = ToxicityMetric(threshold=threshold, model=self._deepeval_model)
        self.threshold = threshold

    @retry_evaluation()
    def evaluate(
        self,
        input: str,
        output: str,
    ) -> MetricResult:
        test_case = self._create_test_case(input=input, output=output)
        self._metric.measure(test_case)
        return MetricResult(
            score=self._metric.score,
            details={
                "reason": self._metric.reason,
                "is_successful": self._metric.is_successful(),
                "threshold": self.threshold,
            },
        )


class DeepEvalNonAdvice(DeepEvalMetricBase):
    """DeepEval implementation of Non-Advice metric."""

    metric_type = MetricType.CLASSIFICATION

    def __init__(
        self,
        advice_types: List[str],
        threshold: float = 0.5,
        model: Optional[Union[BaseLLM, str]] = None,
    ):
        super().__init__(
            name="Non-Advice",
            metric_type=self.metric_type,
            model=model,
        )
        self._metric = NonAdviceMetric(
            advice_types=advice_types, threshold=threshold, model=self._deepeval_model
        )
        self.threshold = threshold

    @retry_evaluation()
    def evaluate(
        self,
        input: str,
        output: str,
    ) -> MetricResult:
        test_case = self._create_test_case(input=input, output=output)
        self._metric.measure(test_case)
        return MetricResult(
            score=self._metric.score,
            details={
                "reason": self._metric.reason,
                "is_successful": self._metric.is_successful(),
                "threshold": self.threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return False


class DeepEvalMisuse(DeepEvalMetricBase):
    """DeepEval implementation of Misuse metric."""

    metric_type = MetricType.CLASSIFICATION

    def __init__(
        self,
        domain: str = "general",
        threshold: float = 0.5,
        model: Optional[Union[BaseLLM, str]] = None,
    ):
        super().__init__(
            name="Misuse",
            metric_type=self.metric_type,
            model=model,
        )
        self._metric = MisuseMetric(domain=domain, threshold=threshold, model=self._deepeval_model)
        self.threshold = threshold

    @retry_evaluation()
    def evaluate(
        self,
        input: str,
        output: str,
    ) -> MetricResult:
        test_case = self._create_test_case(input=input, output=output)
        self._metric.measure(test_case)
        return MetricResult(
            score=self._metric.score,
            details={
                "reason": self._metric.reason,
                "is_successful": self._metric.is_successful(),
                "threshold": self.threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return False


class DeepEvalPIILeakage(DeepEvalMetricBase):
    """DeepEval implementation of PII Leakage metric."""

    metric_type = MetricType.CLASSIFICATION

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="PII Leakage",
            metric_type=self.metric_type,
            model=model,
        )
        self._metric = PIILeakageMetric(threshold=threshold, model=self._deepeval_model)
        self.threshold = threshold

    @retry_evaluation()
    def evaluate(
        self,
        input: str,
        output: str,
    ) -> MetricResult:
        test_case = self._create_test_case(input=input, output=output)
        self._metric.measure(test_case)
        return MetricResult(
            score=self._metric.score,
            details={
                "reason": self._metric.reason,
                "is_successful": self._metric.is_successful(),
                "threshold": self.threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return False


class DeepEvalRoleViolation(DeepEvalMetricBase):
    """DeepEval implementation of Role Violation metric."""

    metric_type = MetricType.CLASSIFICATION

    def __init__(
        self,
        role: str,
        threshold: float = 0.5,
        model: Optional[Union[BaseLLM, str]] = None,
    ):
        super().__init__(
            name="Role Violation",
            metric_type=self.metric_type,
            model=model,
        )
        self._metric = RoleViolationMetric(
            role=role, threshold=threshold, model=self._deepeval_model
        )
        self.threshold = threshold

    @retry_evaluation()
    def evaluate(
        self,
        input: str,
        output: str,
    ) -> MetricResult:
        test_case = self._create_test_case(input=input, output=output)
        self._metric.measure(test_case)
        return MetricResult(
            score=self._metric.score,
            details={
                "reason": self._metric.reason,
                "is_successful": self._metric.is_successful(),
                "threshold": self.threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return False
