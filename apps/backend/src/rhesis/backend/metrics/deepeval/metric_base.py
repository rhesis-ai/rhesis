from typing import Any, Dict, List, Optional, Union

from deepeval.models import (
    AmazonBedrockModel,
    AnthropicModel,
    AzureOpenAIModel,
    GeminiModel,
    GPTModel,
    OllamaModel,
)
from deepeval.test_case import LLMTestCase

from rhesis.backend.metrics.base import BaseMetric, MetricType
from rhesis.backend.metrics.deepeval.model_factory import get_model_from_config


class DeepEvalMetricBase(BaseMetric):
    """Base class for DeepEval metrics with common functionality."""

    def __init__(
        self,
        name: str,
        threshold: float = 0.5,
        metric_type: MetricType = "rag",
        model_config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(name=name, metric_type=metric_type)
        self._metric = None  # Will be set by child classes
        self.threshold = threshold  # Use setter for validation
        self._model = get_model_from_config(model_config)

    @property
    def model(
        self,
    ) -> Union[
        GeminiModel, GPTModel, AzureOpenAIModel, AnthropicModel, AmazonBedrockModel, OllamaModel
    ]:
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
