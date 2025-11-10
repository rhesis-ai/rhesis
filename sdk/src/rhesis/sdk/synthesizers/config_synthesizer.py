"""A synthesizer that generates test cases based on a prompt using LLM."""

from typing import Any, List, Optional, Union

from pydantic import BaseModel

from rhesis.sdk.models.base import BaseLLM
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
        **kwargs: dict[str, Any],
    ):
        """
        Initialize the ConfigSynthesizer.
        Args:
            config: The generation config to use
            batch_size: Maximum number of tests to generate in a single LLM call (reduced default
            for stability)
            system_prompt: Optional custom system prompt template to override the default
        """

        super().__init__(batch_size=batch_size, model=model, sources=sources, **kwargs)
        self.config = config

    def _get_template_context(self, **generate_kwargs):
        return {**self.config.model_dump(), **generate_kwargs}
