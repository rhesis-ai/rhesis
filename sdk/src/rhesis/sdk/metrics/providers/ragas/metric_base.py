from typing import Optional, Union

from ragas.llms import LangchainLLMWrapper

from rhesis.sdk.metrics.base import BaseMetric, MetricType
from rhesis.sdk.metrics.providers.ragas.model import CustomLLM
from rhesis.sdk.models import BaseLLM


class RagasMetricBase(BaseMetric):
    """Base class for Ragas metrics with common functionality."""

    def __init__(
        self,
        name: str,
        threshold: float = 0.5,
        model: Optional[Union[BaseLLM, str]] = None,
        metric_type: MetricType = MetricType.RAG,
    ):
        super().__init__(name=name, metric_type=metric_type, model=model)
        self.threshold = threshold  # Use the setter for validation
        # Actual Ragas implementation to be added
        self.model = LangchainLLMWrapper(CustomLLM(rhesis_model=self.model))

    @property
    def threshold(self) -> float:
        return self._threshold

    @threshold.setter
    def threshold(self, value: float):
        if not 0 <= value <= 1:
            raise ValueError("Threshold must be between 0 and 1")
        self._threshold = value

    def evaluate(self):
        pass
