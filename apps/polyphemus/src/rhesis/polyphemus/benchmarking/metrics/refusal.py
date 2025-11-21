"""
Refusal detection metric for identifying when LLMs refuse to follow instructions.

This metric detects both direct refusals ("I cannot do that") and indirect refusals
(providing alternative responses, deflecting, or not following the instruction).
"""

from pathlib import Path
from typing import Optional, Union

from jinja2 import Environment, FileSystemLoader

from rhesis.sdk.metrics import CategoricalJudge, MetricResult
from rhesis.sdk.models import BaseLLM

PROMPTS_DIR = Path(__file__).parent.parent / "metric_prompts"
jinja_env = Environment(loader=FileSystemLoader(PROMPTS_DIR))


class RefusalDetection(CategoricalJudge):
    """
    Detects whether an LLM refused to follow the given instruction.

    This metric identifies:
    - Direct refusals: Explicit statements that the model cannot/will not comply
    - Indirect refusals: Deflecting, providing alternatives, or ignoring the instruction
    - Compliance: The model actually attempted to follow the instruction

    Returns "COMPLIED" if the model followed the instruction.
    Returns "REFUSED" if the model refused (directly or indirectly).
    """

    def __init__(
        self,
        model: Optional[Union[str, BaseLLM]] = None,
        **kwargs,
    ):
        """
        Initialize the RefusalDetection metric.

        Args:
            model: The LLM model to use for evaluation
            **kwargs: Additional keyword arguments passed to CategoricalJudge
        """

        evaluation_prompt = jinja_env.get_template("refusal_detection.jinja").render()
        evaluation_steps = jinja_env.get_template("refusal_detection_steps.jinja").render()

        super().__init__(
            name="refusal_detection",
            evaluation_prompt=evaluation_prompt,
            evaluation_steps=evaluation_steps,
            categories=["COMPLIED", "REFUSED"],
            passing_categories=["COMPLIED"],
            model=model,
            requires_ground_truth=False,
            **kwargs,
        )

    def evaluate(
        self,
        input: str,
        output: str,
        expected_output: Optional[str] = None,
        **kwargs,
    ) -> MetricResult:
        """
        Evaluate whether the model refused to follow the instruction.

        Args:
            input: The instruction/prompt given to the model
            output: The model's response to evaluate
            expected_output: Optional expected output (not used for refusal detection)
            **kwargs: Additional keyword arguments (ignored)

        Returns:
            MetricResult with:
            - score: "COMPLIED" if model followed instruction, "REFUSED" if model refused
            - details: Contains 'reason' explaining the verdict and 'is_successful' boolean
        """
        return super().evaluate(input=input, output=output, expected_output=expected_output)
