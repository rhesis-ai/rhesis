"""A synthesizer that generates test cases based on a prompt using LLM."""

from typing import List, Optional, Union

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.services.chunker import ChunkingStrategy, SemanticChunker
from rhesis.sdk.services.extractor import SourceSpecification
from rhesis.sdk.synthesizers.base import TestSetSynthesizer


class PromptSynthesizer(TestSetSynthesizer):
    """A synthesizer that generates test cases based on a prompt."""

    prompt_template_file = "prompt_synthesizer.jinja"

    def __init__(
        self,
        prompt: str,
        batch_size: int = 20,
        sources: Optional[List[SourceSpecification]] = None,
        model: Optional[Union[str, BaseLLM]] = None,
        chunking_strategy: Optional[ChunkingStrategy] = SemanticChunker(max_tokens_per_chunk=1500),
    ):
        """
        Initialize the prompt synthesizer.
        Args:
            prompt: The generation prompt to use
            batch_size: Maximum number of tests to generate in a single LLM call
            sources: Optional list of source specifications to use
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

    def _get_template_context(self, **generate_kwargs):
        """
        Prepare template context for _generate_batch() call.

        Combines instance state (self.prompt) with runtime parameters.

        Args:
            **generate_kwargs: Runtime parameters for generation

        Returns:
            Dict containing template context for rendering
        """
        return {
            "generation_prompt": self.prompt,
            **generate_kwargs,
        }
