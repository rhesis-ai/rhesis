from typing import Any, List, Optional, Union

from deepeval.test_case.llm_test_case import LLMTestCase

from rhesis.sdk.metrics.base import BaseMetric, MetricConfig, MetricType, ScoreType
from rhesis.sdk.metrics.providers.deepeval.model import DeepEvalModelWrapper


class DeepEvalMetricBase(BaseMetric):
    """Base class for DeepEval metrics with common functionality."""

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        score_type: Optional[Union[str, ScoreType]] = None,
        metric_type: Optional[Union[str, MetricType]] = None,
        model: Optional[Any] = None,
        requires_context: bool = False,
        requires_ground_truth: bool = False,
    ):
        config = MetricConfig(
            name=name,
            description=description,
            score_type=score_type,
            metric_type=metric_type,
            requires_context=requires_context,
            requires_ground_truth=requires_ground_truth,
        )
        super().__init__(config=config, model=model)
        self._metric = None  # Will be set by child classes
        self._deepeval_model = DeepEvalModelWrapper(self._model)

    @property
    def model(self) -> Any:
        """Get the current model."""
        return self._model

    @model.setter
    def model(self, value: Any):
        """Set the model and update the DeepEval wrapper."""
        self._model = self.set_model(value)
        self._deepeval_model = DeepEvalModelWrapper(self._model)

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
        self,
        input: str,
        output: Optional[str] = None,
        expected_output: Optional[str] = None,
        context: Optional[List[str]] = None,
    ) -> LLMTestCase:
        """Create a DeepEval test case from input parameters."""
        return LLMTestCase(
            input=input,
            actual_output=output,  # type: ignore
            expected_output=expected_output,
            retrieval_context=context,
        )
