"""
Context Retention metric for evaluating correct usage of provided context.
Matches SDK patterns by accepting context as List[str].
"""

from pathlib import Path
from typing import List, Optional, Union

from jinja2 import Environment, FileSystemLoader

from rhesis.sdk.metrics import MetricResult, NumericJudge
from rhesis.sdk.models import BaseLLM

PROMPTS_DIR = Path(__file__).parent.parent / "metric_prompts"
jinja_env = Environment(loader=FileSystemLoader(PROMPTS_DIR))


class ContextRetentionJudge(NumericJudge):
    """
    Evaluates whether the model correctly used the provided context.

    This metric assesses how well the output incorporates and respects
    information from the provided context chunks (RAG-style evaluation).

    Matches SDK patterns:
    - Accepts context as List[str] (list of context chunks)
    - Joins chunks with newlines for evaluation prompt
    - Uses NumericJudge base class with comprehensive evaluation criteria

    Score interpretation:
    - 1.0: Perfect context usage - all relevant info incorporated, no contradictions
    - 0.7-0.9: Strong usage - most context used correctly, minor omissions
    - 0.4-0.6: Partial usage - some context used but significant gaps/issues
    - 0.0-0.3: Poor usage - context ignored, contradicted, or fabricated info
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
        Initialize the ContextRetentionJudge metric.

        Args:
            min_score: Minimum possible score (defaults to 0)
            max_score: Maximum possible score (defaults to 1)
            threshold: Success threshold (defaults to 0.7)
            model: The LLM model to use for evaluation
            **kwargs: Additional keyword arguments passed to NumericJudge
        """
        evaluation_prompt = jinja_env.get_template("context_retention.jinja").render()
        evaluation_steps = jinja_env.get_template("context_retention_steps.jinja").render()
        evaluation_examples = jinja_env.get_template("context_retention_examples.jinja").render()

        super().__init__(
            name="context_retention",
            evaluation_prompt=evaluation_prompt,
            evaluation_steps=evaluation_steps,
            evaluation_examples=evaluation_examples,
            min_score=min_score if min_score is not None else 0.0,
            max_score=max_score if max_score is not None else 1.0,
            threshold=threshold if threshold is not None else 0.7,
            model=model,
            requires_context=True,
            **kwargs,
        )

    def evaluate(
        self,
        input: str,
        output: str,
        expected_output: Optional[str] = None,
        context: Optional[List[str]] = None,
        **kwargs,
    ) -> MetricResult:
        """
        Evaluate context retention with SDK-compatible interface.

        Args:
            input: The input query/prompt
            output: The model's response to evaluate
            expected_output: Optional expected response
            context: List of context chunks (SDK format)
            **kwargs: Additional arguments

        Returns:
            MetricResult with score (0-1) and explanation
        """
        # Convert context list to format expected by parent class
        # The SDK's NumericJudge expects context as List[str] and handles joining internally
        return super().evaluate(
            input=input,
            output=output,
            expected_output=expected_output,
            context=context,
            **kwargs,
        )
