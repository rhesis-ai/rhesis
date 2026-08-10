"""Synthesize metric definitions from natural-language descriptions."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, Field

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import get_model

logger = logging.getLogger(__name__)

_ASSETS_DIR = Path(__file__).parent / "assets"


class GeneratedMetric(BaseModel):
    """Schema the LLM fills in when synthesizing a metric."""

    name: str = Field(
        description=(
            "Short, unique metric name in Title Case with spaces "
            '(e.g. "Factual Accuracy", "Response Completeness")'
        )
    )
    description: str = Field(description="One-sentence explanation of what the metric measures")
    evaluation_prompt: str = Field(
        description=(
            "Evaluation criteria text only — no template placeholders. "
            "The evaluation engine injects runtime context automatically. "
            "For single-turn metrics, focus on response-level criteria "
            "(accuracy, relevance, safety). For multi-turn metrics, focus "
            "on conversation-level criteria (goal achievement, turn "
            "progression, coherence across turns)."
        )
    )
    evaluation_steps: str = Field(
        description=(
            "Numbered step-by-step instructions the judge LLM follows to "
            'reach a score (e.g. "1. Identify each factual claim. '
            "2. Check it against the provided context. 3. Count "
            'unsupported claims. 4. Map the count to the scale."). '
            "Concrete steps make scoring far more repeatable than "
            "criteria prose alone."
        )
    )
    reasoning: str = Field(
        description=(
            "Instructions for how the judge should explain its verdict — "
            "what evidence to cite and how to justify the score it gives."
        )
    )
    explanation: str = Field(
        description=(
            "What a passing versus failing result means for the system "
            "under test, so whoever reads a result knows what to do "
            "about it."
        )
    )
    score_type: str = Field(description='Must be exactly "numeric" or "categorical"')
    min_score: Optional[float] = Field(
        default=None,
        description="Minimum score value (numeric metrics only)",
    )
    max_score: Optional[float] = Field(
        default=None,
        description="Maximum score value (numeric metrics only)",
    )
    threshold: Optional[float] = Field(
        default=None,
        description="Pass/fail threshold (numeric metrics only)",
    )
    threshold_operator: Optional[str] = Field(
        default=None,
        description=(
            "Comparison operator for threshold. One of: "
            '"=", "<", ">", "<=", ">=", "!=". '
            "Only used for numeric metrics."
        ),
    )
    categories: Optional[List[str]] = Field(
        default=None,
        description=(
            "Valid category labels (categorical metrics only). "
            "Must be non-empty when score_type is categorical."
        ),
    )
    passing_categories: Optional[List[str]] = Field(
        default=None,
        description=("Subset of categories that indicate a pass (categorical metrics only)"),
    )
    metric_scope: Optional[List[str]] = Field(
        default=None,
        description=(
            'Non-empty list containing "Single-Turn" and/or "Multi-Turn". Always '
            "provide it. This decides which tests the metric is evaluated against, "
            "so a wrong value means it silently never runs. Use [\"Multi-Turn\"] for "
            'metrics that judge a whole conversation, ["Single-Turn"] for a single '
            "request-response exchange, and both only when it genuinely works either way."
        ),
    )


class MetricSynthesizer:
    """Synthesize a metric definition from a natural-language description.

    Uses an LLM with a Jinja prompt template to produce all required
    metric fields (name, evaluation_prompt, score_type, thresholds, etc.).

    Example::

        synth = MetricSynthesizer()
        metric_dict = synth.generate(
            "Measure factual accuracy on a 1-5 numeric scale"
        )
    """

    TEMPLATE_FILE = "generate_metric.jinja"
    IMPROVE_TEMPLATE_FILE = "improve_metric.jinja"

    def __init__(
        self,
        model: Optional[Union[str, BaseLLM]] = None,
    ):
        env = Environment(loader=FileSystemLoader(str(_ASSETS_DIR)))
        self.prompt_template = env.get_template(self.TEMPLATE_FILE)
        self.improve_template = env.get_template(self.IMPROVE_TEMPLATE_FILE)

        if isinstance(model, str) or model is None:
            self.model = get_model(model)
        else:
            self.model = model

    def generate(self, prompt: str) -> Dict[str, Any]:
        """Generate a metric definition from a natural-language prompt.

        Args:
            prompt: Natural-language description of the desired metric.

        Returns:
            Dictionary of metric fields suitable for ``MetricCreate``
            or the ``Metric`` entity constructor.

        Raises:
            RuntimeError: If the LLM returns an error response.
        """
        rendered = self.prompt_template.render(prompt=prompt)

        logger.info(
            "[MetricSynthesizer] Generating metric from prompt (prompt_length=%d, model=%s)",
            len(rendered),
            getattr(self.model, "model_name", type(self.model).__name__),
        )

        response = self.model.generate(rendered, schema=GeneratedMetric)

        if isinstance(response, dict) and "error" in response:
            raise RuntimeError(str(response["error"]))
        if isinstance(response, dict):
            return response
        return response.model_dump()

    def improve(self, existing_metric: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        """Improve an existing metric based on natural-language instructions.

        Args:
            existing_metric: Dictionary of the current metric fields.
            prompt: Natural-language edit instructions
                (e.g. "make the threshold stricter").

        Returns:
            Dictionary of updated metric fields.

        Raises:
            RuntimeError: If the LLM returns an error response.
        """
        rendered = self.improve_template.render(
            existing_metric=existing_metric,
            prompt=prompt,
        )

        logger.info(
            "[MetricSynthesizer] Improving metric '%s' (prompt_length=%d, model=%s)",
            existing_metric.get("name", "?"),
            len(rendered),
            getattr(self.model, "model_name", type(self.model).__name__),
        )

        response = self.model.generate(rendered, schema=GeneratedMetric)

        if isinstance(response, dict) and "error" in response:
            raise RuntimeError(str(response["error"]))
        if isinstance(response, dict):
            return response
        return response.model_dump()
