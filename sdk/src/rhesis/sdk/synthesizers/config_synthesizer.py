"""A synthesizer that generates test cases based on a prompt using LLM."""

import logging
from dataclasses import asdict, dataclass
from typing import List, Optional, Union

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.synthesizers.base import TestSetSynthesizer

logger = logging.getLogger(__name__)


@dataclass
class GenerationConfig:
    """Dataclass representing generation config information."""

    behaviors: List[str]  # Behaviors
    categories: List[str]  # Categories
    topics: List[str]  # Topics

    project_context: str  # Select project
    specific_requirements: str  # Describe what you want to test

    previous_messages: List[str]  # Previous messages
    rated_samples: List[str]  # Rated samples

    test_type: str  # Test type
    output_format: str  # Output format


class ConfigSynthesizer(TestSetSynthesizer):
    """A synthesizer that generates test cases based on a generation config using LLM."""

    prompt_template_file = "config_synthesizer.jinja"

    def __init__(
        self,
        config: GenerationConfig,
        batch_size: int = 20,
        model: Optional[Union[str, BaseLLM]] = None,
    ):
        """
        Initialize the ConfigSynthesizer.
        Args:
            config: The generation config to use
            batch_size: Maximum number of tests to generate in a single LLM call (reduced default
            for stability)
            system_prompt: Optional custom system prompt template to override the default
        """

        super().__init__(batch_size=batch_size, model=model)
        self.config = config

    def _get_template_context(self, **generate_kwargs):
        return {**asdict(self.config), **generate_kwargs}
