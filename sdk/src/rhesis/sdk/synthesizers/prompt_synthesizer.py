"""A synthesizer that generates test cases based on a prompt using LLM."""

from typing import Any, Optional, Union

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.synthesizers.base import TestSetSynthesizer


class PromptSynthesizer(TestSetSynthesizer):
    """A synthesizer that generates test cases based on a prompt using LLM."""

    prompt_template_file = "simple_synthesizer.jinja"

    def __init__(
        self,
        prompt: str,
        batch_size: int = 20,
        model: Optional[Union[str, BaseLLM]] = None,
        **kwargs: dict[str, Any],
    ):
        """
        Initialize the simple synthesizer.
        Args:
            prompt: The generation prompt to use
            batch_size: Maximum number of tests to generate in a single LLM call (reduced default
            for stability)
        """

        super().__init__(batch_size=batch_size, model=model, **kwargs)
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
        return {"generation_prompt": self.prompt, **generate_kwargs}
