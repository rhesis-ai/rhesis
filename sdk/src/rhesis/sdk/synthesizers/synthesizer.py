"""A synthesizer that generates test cases based on a prompt using LLM."""

from typing import List, Optional, Union

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.services.chunker import ChunkingStrategy, SemanticChunker
from rhesis.sdk.services.extractor import SourceSpecification
from rhesis.sdk.synthesizers.base import TestSetSynthesizer


class Synthesizer(TestSetSynthesizer):
    """A synthesizer that generates test cases based on a user specification."""

    prompt_template_file = "synthesizer.jinja"

    def __init__(
        self,
        prompt: str,
        behaviors: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        sources: Optional[List[SourceSpecification]] = None,
        batch_size: int = 20,
        model: Optional[Union[str, BaseLLM]] = None,
        chunking_strategy: Optional[ChunkingStrategy] = SemanticChunker(max_tokens_per_chunk=1500),
    ):
        """
        Initialize the synthesizer.
        Args:
            prompt: The generation prompt to use
            behaviors: List of behaviors to test
            categories: List of categories to test
            topics: List of topics to test
            sources: List of source specifications to use
            batch_size: Maximum number of tests to generate in a single LLM call
            model: The model to use for generation
            chunking_strategy: Strategy for chunking source content
        """

        super().__init__(
            batch_size=batch_size,
            model=model,
            sources=sources,
            chunking_strategy=chunking_strategy,
        )
        self.prompt = prompt
        self.behaviors = behaviors
        self.categories = categories
        self.topics = topics

    def _get_template_context(self, **generate_kwargs):
        """
        Prepare template context for _generate_batch() call.

        Combines instance state (self.prompt, behaviors, categories, topics)
        with runtime parameters.

        Args:
            **generate_kwargs: Runtime parameters for generation

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
