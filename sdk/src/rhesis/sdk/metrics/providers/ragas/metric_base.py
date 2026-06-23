import logging
from typing import Any, Optional, Union

from ragas.llms import LangchainLLMWrapper

from rhesis.sdk.metrics.base import BaseMetric, MetricConfig, MetricResult, MetricType, ScoreType
from rhesis.sdk.metrics.providers.ragas.model import CustomLLM

logger = logging.getLogger(__name__)


class RagasMetricBase(BaseMetric):
    """Base class for Ragas metrics with common functionality."""

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

        self._ragas_model = LangchainLLMWrapper(CustomLLM(rhesis_model=self.model))

    @property
    def model(self) -> Any:
        """Get the current model."""
        return self._model

    @model.setter
    def model(self, value: Any):
        """Set the model and update the Ragas wrapper."""
        self._model = self.set_model(value)
        self._ragas_model = LangchainLLMWrapper(CustomLLM(rhesis_model=self._model))

    async def _safe_single_turn_ascore(self, scorer, sample) -> Optional[float]:
        """Score a sample, returning None on output-parse failures.

        RAGAS metrics require the LLM to produce structured JSON matching
        specific Pydantic schemas. Models with weak instruction-following
        (e.g. Gemma, smaller open-source models on vLLM) often fail to
        produce valid output, triggering RAGAS's internal fix-and-retry
        loop before ultimately raising an OutputParserException. Catching
        these here avoids noisy tracebacks and wasted LLM calls from the
        outer retry layer.
        """
        try:
            from langchain_core.exceptions import OutputParserException
        except ImportError:
            OutputParserException = None

        try:
            from ragas.exceptions import RagasOutputParserException
        except ImportError:
            RagasOutputParserException = None

        catch_types = tuple(
            t for t in (OutputParserException, RagasOutputParserException) if t is not None
        )
        if not catch_types:
            return await scorer.single_turn_ascore(sample)

        try:
            return await scorer.single_turn_ascore(sample)
        except catch_types as exc:
            logger.warning(
                "RAGAS metric '%s' could not parse model output "
                "(model may not support structured JSON output required by this metric): %s",
                self.name,
                exc,
            )
            return None

    def _output_parse_error_result(self, threshold: float) -> MetricResult:
        """Return a MetricResult for output-parse failures."""
        return MetricResult(
            score=0.0,
            details={
                "reason": (
                    f"Metric '{self.name}' failed: the evaluation model could not produce "
                    "structured output required by this metric. This commonly happens with "
                    "smaller or local models (e.g. Gemma on vLLM) that have limited "
                    "instruction-following for JSON schemas. Consider using a more capable "
                    "model for metric evaluation."
                ),
                "is_successful": False,
                "threshold": threshold,
                "inconclusive": True,
            },
        )
