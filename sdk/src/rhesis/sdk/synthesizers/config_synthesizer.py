"""A synthesizer that generates test cases based on a prompt using LLM."""

from typing import List, Optional, Union

from pydantic import BaseModel

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.services.chunker import ChunkingStrategy, SemanticChunker
from rhesis.sdk.services.extractor import SourceSpecification
from rhesis.sdk.synthesizers.base import TestSetSynthesizer


class GenerationConfig(BaseModel):
    """Dataclass representing generation config information."""

    generation_prompt: Optional[str] = None  # Describe what you want to test

    behaviors: Optional[List[str]] = None  # Behaviors
    categories: Optional[List[str]] = None  # Categories
    topics: Optional[List[str]] = None  # Topics

    additional_context: Optional[str] = None  # Additional context


class ConfigSynthesizer(TestSetSynthesizer):
    """A synthesizer that generates test cases based on a generation config using LLM."""

    prompt_template_file = "config_synthesizer.jinja"

    def __init__(
        self,
        config: GenerationConfig,
        batch_size: int = 20,
        model: Optional[Union[str, BaseLLM]] = None,
        sources: Optional[List[SourceSpecification]] = None,
        chunking_strategy: Optional[ChunkingStrategy] = SemanticChunker(max_tokens_per_chunk=1500),
    ):
        """
        Initialize the ConfigSynthesizer.
        Args:
            config: The generation config to use
            batch_size: Maximum number of tests to generate in a single LLM call
            model: The model to use for generation
            sources: Optional list of source specifications to use
            chunking_strategy: Strategy for chunking source content
        """

        super().__init__(
            batch_size=batch_size,
            model=model,
            sources=sources,
            chunking_strategy=chunking_strategy,
        )
        self.config = config

    def _get_template_context(self, **generate_kwargs):
        """
        Prepare template context for _generate_batch() call.

        Combines config state with runtime parameters.

        Args:
            **generate_kwargs: Runtime parameters for generation

        Returns:
            Dict containing template context for rendering
        """
        return {**self.config.model_dump(), **generate_kwargs}
