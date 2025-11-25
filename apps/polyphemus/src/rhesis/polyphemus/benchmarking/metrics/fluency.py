"""
Fluency metric for evaluating grammar, coherence, and naturalness of LLM outputs.
"""

from pathlib import Path
from typing import Optional, Union

from jinja2 import Environment, FileSystemLoader

from rhesis.sdk.metrics import NumericJudge
from rhesis.sdk.models import BaseLLM

PROMPTS_DIR = Path(__file__).parent.parent / "metric_prompts"
jinja_env = Environment(loader=FileSystemLoader(PROMPTS_DIR))


class FluencyJudge(NumericJudge):
    """
    Evaluates the fluency of text based on grammar, coherence, and naturalness.

    This metric assesses how well-written and natural the output text is,
    considering grammatical correctness, logical flow, and overall readability.

    Inherits from NumericJudge with prepopulated evaluation criteria.
    """

    def __init__(
        self,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        threshold: Optional[float] = None,
        model: Optional[Union[str, BaseLLM]] = None,
        **kwargs,
    ):
        """
        Initialize the FluencyJudge metric.

        Args:
            min_score: Minimum possible score (defaults to 0)
            max_score: Maximum possible score (defaults to 1)
            threshold: Success threshold (defaults to midpoint)
            model: The LLM model to use for evaluation
            **kwargs: Additional keyword arguments passed to NumericJudge
        """
        evaluation_prompt = jinja_env.get_template("fluency.jinja").render()
        evaluation_steps = jinja_env.get_template("fluency_steps.jinja").render()

        super().__init__(
            name="fluency",
            evaluation_prompt=evaluation_prompt,
            evaluation_steps=evaluation_steps,
            min_score=min_score,
            max_score=max_score,
            threshold=threshold,
            model=model,
            **kwargs,
        )
