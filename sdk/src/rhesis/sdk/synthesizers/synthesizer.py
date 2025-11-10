"""A synthesizer that generates test cases based on a prompt using LLM."""

from typing import Any, List, Optional, Union

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.services.extractor import SourceSpecification
from rhesis.sdk.synthesizers.base import TestSetSynthesizer


class Synthesizer(TestSetSynthesizer):
    """A synthesizer that generates test cases based on a user specification."""

    prompt_template_file = "synthesizer.jinja"

    def __init__(
        self,
        prompt: str,
        behaviors: List[str],
        categories: List[str],
        topics: List[str],
        sources: List[SourceSpecification],
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

        super().__init__(batch_size=batch_size, model=model, sources=sources, **kwargs)
        self.prompt = prompt
        self.behaviors = behaviors
        self.categories = categories
        self.topics = topics

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
        return {
            "generation_prompt": self.prompt,
            "behaviors": self.behaviors,
            "categories": self.categories,
            "topics": self.topics,
            **generate_kwargs,
        }
