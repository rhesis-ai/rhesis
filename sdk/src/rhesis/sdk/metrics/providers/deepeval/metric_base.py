from typing import List, Optional, Union

from deepeval.test_case import LLMTestCase

from rhesis.sdk.metrics.base import BaseMetric, MetricType
from rhesis.sdk.metrics.providers.deepeval.model import DeepEvalModelWrapper

# from rhesis.sdk.metrics.providers.deepeval.model_factory import get_model_from_config
from rhesis.sdk.models.base import BaseLLM


class DeepEvalMetricBase(BaseMetric):
    """Base class for DeepEval metrics with common functionality."""

    def __init__(
        self,
        name: str,
        threshold: float = 0.5,
        metric_type: MetricType = "rag",
        model: Optional[Union[BaseLLM, str]] = None,
    ):
        super().__init__(name=name, metric_type=metric_type, model=model)
        self._metric = None  # Will be set by child classes
        self.threshold = threshold  # Use setter for validation
        self._model = DeepEvalModelWrapper(self._model)

    @property
    def model(self) -> BaseLLM:
        """Get the configured model instance."""
        return self._model

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
