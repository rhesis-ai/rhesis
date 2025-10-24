from typing import Any, Optional, Union

from ragas.llms import LangchainLLMWrapper

from rhesis.sdk.metrics.base import BaseMetric, MetricConfig, MetricType, ScoreType
from rhesis.sdk.metrics.providers.ragas.model import CustomLLM


class RagasMetricBase(BaseMetric):
    """Base class for Ragas metrics with common functionality."""

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        score_type: Optional[Union[str, ScoreType]] = None,
        metric_type: Optional[Union[str, MetricType]] = None,
        model: Optional[Any] = None,
    ):
        config = MetricConfig(
            name=name,
            description=description,
            score_type=score_type,
            metric_type=metric_type,
        )
        super().__init__(config=config, model=model)
        self.model = LangchainLLMWrapper(CustomLLM(rhesis_model=self.model))
