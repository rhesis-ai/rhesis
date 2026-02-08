from typing import List, Optional, Union

from rhesis.sdk.metrics.base import MetricResult, MetricType
from rhesis.sdk.metrics.providers.deepeval.metric_base import DeepEvalMetricBase
from rhesis.sdk.metrics.utils import retry_evaluation
from rhesis.sdk.models.base import BaseLLM


class DeepEvalAnswerRelevancy(DeepEvalMetricBase):
    """DeepEval implementation of Answer Relevancy metric."""

    metric_type = MetricType.RAG
    requires_ground_truth = False
    requires_context = False

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="Answer Relevancy",
            metric_type=self.metric_type,
            model=model,
            requires_context=self.requires_context,
            requires_ground_truth=self.requires_ground_truth,
        )
        from deepeval.metrics import AnswerRelevancyMetric  # type: ignore

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


class DeepEvalFaithfulness(DeepEvalMetricBase):
    """DeepEval implementation of Faithfulness metric."""

    metric_type = MetricType.RAG
    requires_ground_truth = False
    requires_context = True

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="Faithfulness",
            metric_type=self.metric_type,
            model=model,
            requires_context=self.requires_context,
            requires_ground_truth=self.requires_ground_truth,
        )
        from deepeval.metrics import FaithfulnessMetric  # type: ignore

        self._metric = FaithfulnessMetric(threshold=threshold, model=self._deepeval_model)
        self.threshold = threshold

    @retry_evaluation()
    def evaluate(
        self,
        input: str,
        output: str,
        context: Optional[List[str]] = None,
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


class DeepEvalContextualRelevancy(DeepEvalMetricBase):
    """DeepEval implementation of Contextual Relevancy metric."""

    metric_type = MetricType.RAG
    requires_ground_truth = False
    requires_context = True

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="Contextual Relevancy",
            metric_type=self.metric_type,
            model=model,
            requires_context=self.requires_context,
            requires_ground_truth=self.requires_ground_truth,
        )
        from deepeval.metrics import ContextualRelevancyMetric  # type: ignore

        self._metric = ContextualRelevancyMetric(threshold=threshold, model=self._deepeval_model)
        self.threshold = threshold

    @retry_evaluation()
    def evaluate(
        self,
        input: str,
        context: Optional[List[str]] = None,
    ) -> MetricResult:
        # Validate that context is provided
        if not context or len(context) == 0:
            return MetricResult(
                score=0.0,
                details={
                    "reason": (
                        "Contextual Relevancy metric requires context to evaluate. "
                        "No context was provided."
                    ),
                    "is_successful": False,
                    "threshold": self.threshold,
                },
            )
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


class DeepEvalContextualPrecision(DeepEvalMetricBase):
    """DeepEval implementation of Contextual Precision metric."""

    metric_type = MetricType.RAG
    requires_ground_truth = True
    requires_context = True

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="Contextual Precision",
            metric_type=self.metric_type,
            model=model,
            requires_context=self.requires_context,
            requires_ground_truth=self.requires_ground_truth,
        )
        from deepeval.metrics import ContextualPrecisionMetric  # type: ignore

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
        # Validate that context is provided
        if not context or len(context) == 0:
            return MetricResult(
                score=0.0,
                details={
                    "reason": (
                        "Contextual Precision metric requires context to evaluate. "
                        "No context was provided."
                    ),
                    "is_successful": False,
                    "threshold": self.threshold,
                },
            )
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


class DeepEvalContextualRecall(DeepEvalMetricBase):
    """DeepEval implementation of Contextual Recall metric."""

    metric_type = MetricType.RAG
    requires_ground_truth = True
    requires_context = True

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="Contextual Recall",
            metric_type=self.metric_type,
            model=model,
            requires_context=self.requires_context,
            requires_ground_truth=self.requires_ground_truth,
        )
        from deepeval.metrics import ContextualRecallMetric  # type: ignore

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
        # Validate that context is provided
        if not context or len(context) == 0:
            return MetricResult(
                score=0.0,
                details={
                    "reason": (
                        "Contextual Recall metric requires context to evaluate. "
                        "No context was provided."
                    ),
                    "is_successful": False,
                    "threshold": self.threshold,
                },
            )
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


class DeepEvalBias(DeepEvalMetricBase):
    """DeepEval implementation of Bias metric."""

    metric_type = MetricType.CLASSIFICATION
    requires_ground_truth = False
    requires_context = False

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="Bias",
            metric_type=self.metric_type,
            model=model,
            requires_context=self.requires_context,
            requires_ground_truth=self.requires_ground_truth,
        )
        from deepeval.metrics import BiasMetric  # type: ignore

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


class DeepEvalToxicity(DeepEvalMetricBase):
    """DeepEval implementation of Toxicity metric."""

    metric_type = MetricType.CLASSIFICATION
    requires_ground_truth = False
    requires_context = False

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="Toxicity",
            metric_type=self.metric_type,
            model=model,
            requires_context=self.requires_context,
            requires_ground_truth=self.requires_ground_truth,
        )
        from deepeval.metrics import ToxicityMetric  # type: ignore

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
    requires_ground_truth = False
    requires_context = False

    def __init__(
        self,
        advice_types: Optional[List[str]] = None,
        threshold: float = 0.5,
        model: Optional[Union[BaseLLM, str]] = None,
    ):
        super().__init__(
            name="Non-Advice",
            metric_type=self.metric_type,
            model=model,
            requires_context=self.requires_context,
            requires_ground_truth=self.requires_ground_truth,
        )
        from deepeval.metrics import NonAdviceMetric  # type: ignore

        # Default to common advice types if not provided
        if advice_types is None:
            advice_types = ["legal", "medical", "financial"]
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


class DeepEvalMisuse(DeepEvalMetricBase):
    """DeepEval implementation of Misuse metric."""

    metric_type = MetricType.CLASSIFICATION
    requires_ground_truth = False
    requires_context = False

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
            requires_context=self.requires_context,
            requires_ground_truth=self.requires_ground_truth,
        )
        from deepeval.metrics import MisuseMetric  # type: ignore

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


class DeepEvalPIILeakage(DeepEvalMetricBase):
    """DeepEval implementation of PII Leakage metric."""

    metric_type = MetricType.CLASSIFICATION
    requires_ground_truth = False
    requires_context = False

    def __init__(self, threshold: float = 0.5, model: Optional[Union[BaseLLM, str]] = None):
        super().__init__(
            name="PII Leakage",
            metric_type=self.metric_type,
            model=model,
            requires_context=self.requires_context,
            requires_ground_truth=self.requires_ground_truth,
        )
        from deepeval.metrics import PIILeakageMetric  # type: ignore

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


class DeepEvalRoleViolation(DeepEvalMetricBase):
    """DeepEval implementation of Role Violation metric."""

    metric_type = MetricType.CLASSIFICATION
    requires_ground_truth = False
    requires_context = False

    def __init__(
        self,
        role: Optional[str] = None,
        threshold: float = 0.5,
        model: Optional[Union[BaseLLM, str]] = None,
    ):
        super().__init__(
            name="Role Violation",
            metric_type=self.metric_type,
            model=model,
            requires_context=self.requires_context,
            requires_ground_truth=self.requires_ground_truth,
        )
        from deepeval.metrics import RoleViolationMetric  # type: ignore

        # Default to a generic helpful assistant role if not provided
        if role is None:
            role = "helpful assistant"
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


class DeepTeamIllegal(DeepEvalMetricBase):
    """DeepTeam implementation of Illegal metric."""

    metric_type = MetricType.CLASSIFICATION
    requires_ground_truth = False
    requires_context = False

    def __init__(
        self,
        illegal_category: Optional[str] = None,
        model: Optional[Union[BaseLLM, str]] = None,
    ):
        super().__init__(
            name="Illegal",
            metric_type=self.metric_type,
            model=model,
            requires_context=self.requires_context,
            requires_ground_truth=self.requires_ground_truth,
        )
        from deepteam.metrics import IllegalMetric  # type: ignore

        # Use a sensible default if no category is provided
        category = illegal_category or "general"
        self._metric = IllegalMetric(illegal_category=category, model=self._deepeval_model)
        self.illegal_category = category

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
            },
        )


class DeepTeamSafety(DeepEvalMetricBase):
    """DeepTeam implementation of Safety metric."""

    metric_type = MetricType.CLASSIFICATION
    requires_ground_truth = False
    requires_context = False

    def __init__(
        self,
        safety_category: Optional[str] = None,
        model: Optional[Union[BaseLLM, str]] = None,
    ):
        super().__init__(
            name="Safety",
            metric_type=self.metric_type,
            model=model,
            requires_context=self.requires_context,
            requires_ground_truth=self.requires_ground_truth,
        )
        from deepteam.metrics import SafetyMetric  # type: ignore

        # Use a sensible default if no category is provided
        category = safety_category or "general"
        self._metric = SafetyMetric(safety_category=category, model=self._deepeval_model)
        self.safety_category = category

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
            },
        )
