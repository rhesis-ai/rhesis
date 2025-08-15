"""
Synthesizer factory for creating SDK synthesizer instances dynamically.

This module provides a factory pattern for creating different types of test set synthesizers
based on enum values, allowing for type-safe and extensible synthesizer instantiation.
"""

from enum import Enum
from typing import Any, Dict, Type

import rhesis.sdk
from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.synthesizers.base import TestSetSynthesizer
from rhesis.sdk.synthesizers.paraphrasing_synthesizer import ParaphrasingSynthesizer
from rhesis.sdk.synthesizers.prompt_synthesizer import PromptSynthesizer


class SynthesizerType(str, Enum):
    """Enum for available synthesizer types."""

    PROMPT = "prompt"
    PARAPHRASING = "paraphrasing"


class SynthesizerFactory:
    """Factory class for creating synthesizer instances dynamically."""

    # Mapping of synthesizer types to their corresponding classes
    _SYNTHESIZER_CLASSES: Dict[SynthesizerType, Type[TestSetSynthesizer]] = {
        SynthesizerType.PROMPT: PromptSynthesizer,
        SynthesizerType.PARAPHRASING: ParaphrasingSynthesizer,
    }

    @classmethod
    def create_synthesizer(
        cls, synthesizer_type: SynthesizerType, batch_size: int = 20, **kwargs: Any
    ) -> TestSetSynthesizer:
        """
        Create a synthesizer instance based on the synthesizer type.

        Args:
            synthesizer_type: The type of synthesizer to create
            batch_size: Batch size for the synthesizer
            **kwargs: Additional arguments specific to the synthesizer type
                For PromptSynthesizer: prompt (str, required)
                For ParaphrasingSynthesizer: test_set (TestSet, required)

        Returns:
            TestSetSynthesizer: An instance of the requested synthesizer

        Raises:
            ValueError: If the synthesizer type is not supported or required arguments are missing
        """
        if synthesizer_type not in cls._SYNTHESIZER_CLASSES:
            supported_types = ", ".join([t.value for t in cls._SYNTHESIZER_CLASSES.keys()])
            raise ValueError(
                f"Unsupported synthesizer type: {synthesizer_type}."
                f"Supported types: {supported_types}"
            )

        synthesizer_class = cls._SYNTHESIZER_CLASSES[synthesizer_type]

        # Validate and prepare arguments based on synthesizer type
        if synthesizer_type == SynthesizerType.PROMPT:
            if "prompt" not in kwargs:
                raise ValueError("'prompt' argument is required for PromptSynthesizer")
            return synthesizer_class(prompt=kwargs["prompt"], batch_size=batch_size)

        elif synthesizer_type == SynthesizerType.PARAPHRASING:
            if "test_set" not in kwargs:
                raise ValueError("'test_set' argument is required for ParaphrasingSynthesizer")
            return synthesizer_class(test_set=kwargs["test_set"], batch_size=batch_size)

        # This should never be reached given the validation above, but adding for completeness
        raise ValueError(f"Unknown synthesizer configuration for type: {synthesizer_type}")

    @classmethod
    def get_supported_types(cls) -> list[str]:
        """Get a list of supported synthesizer types."""
        return [t.value for t in cls._SYNTHESIZER_CLASSES.keys()]

    @classmethod
    def configure_sdk(cls, base_url: str, api_key: str) -> None:
        """
        Configure the SDK with the provided settings.

        Args:
            base_url: The base URL for the Rhesis API
            api_key: The API key for authentication
        """
        rhesis.sdk.base_url = base_url
        rhesis.sdk.api_key = api_key

    @classmethod
    def load_source_test_set(cls, test_set_id: str) -> TestSet:
        """
        Load a test set from the API for use with synthesizers.

        Args:
            test_set_id: The ID of the test set to load

        Returns:
            TestSet: The loaded test set with tests populated
        """
        source_test_set = TestSet(id=test_set_id)
        source_test_set.get_tests()  # Load the tests
        return source_test_set
