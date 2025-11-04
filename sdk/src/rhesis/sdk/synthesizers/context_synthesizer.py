"""A synthesizer that generates test cases based on a prompt using LLM."""

import logging
from typing import Optional, Union

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.synthesizers.base import TestSetSynthesizer

logger = logging.getLogger(__name__)


class ContextSynthesizer(TestSetSynthesizer):
    """A synthesizer that generates test cases based on a prompt using LLM."""

    prompt_template_file = "context_synthesizer.jinja"

    def __init__(
        self,
        prompt: str,
        batch_size: int = 20,
        model: Optional[Union[str, BaseLLM]] = None,
    ):
        """
        Initialize the context synthesizer.
        Args:
            prompt: The generation prompt to use
            context: The context to use
            batch_size: Maximum number of tests to generate in a single LLM call (reduced default
            for stability)
        """

        super().__init__(batch_size=batch_size, model=model)
        self.prompt = prompt

    def _get_template_context(self, **generate_kwargs):
        """
        Prepare template context for _generate_batch() call.

        Combines instance state (self.prompt) with runtime parameters.
        SimpleSynthesizer only uses instance state.

        Args:
            **generate_kwargs: Runtime parameters (unused for SimpleSynthesizer)

        Returns:
            Dict containing template context for rendering
        """
        if "context" not in generate_kwargs:
            raise ValueError("Context is required")
        if len(generate_kwargs["context"]) == 0:
            raise ValueError("Context cannot be empty")

        return {"generation_prompt": self.prompt, "context": generate_kwargs["context"]}


if __name__ == "__main__":
    synthesizer = ContextSynthesizer(
        prompt="Test knowledge of the chatbot about Poland", model="gemini"
    )
    context = [
        "Poland is a country in Europe",
        "Warsaw is the capital of Poland",
        "Polish is the official language of Poland",
    ]
    tests = synthesizer.generate(context=context, num_tests=5)
    from pprint import pprint

    pprint(tests.tests)
