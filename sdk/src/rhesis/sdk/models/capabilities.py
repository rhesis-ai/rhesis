"""Model capability detection for multimodal features.

This module provides capability detection to determine what modalities
(vision, audio, video, PDFs) a given model supports, using LiteLLM's
built-in capability detection functions.

Example:
    Checking model capabilities::

        >>> from rhesis.sdk.models import get_model
        >>> model = get_model("gemini", "gemini-2.0-flash")
        >>> print(f"Vision: {model.supports_vision}")
        Vision: True
        >>> print(f"Audio: {model.supports_audio}")
        Audio: True
        >>> caps = model.get_capabilities()
        >>> print(f"Modalities: {caps.supported_modalities}")
        Modalities: {'text', 'image', 'pdf', 'audio', 'video'}
"""

from abc import ABC
from dataclasses import dataclass, field
from typing import Optional, Set

import litellm

__all__ = [
    "ModelCapabilities",
    "CapabilityMixin",
]


@dataclass
class ModelCapabilities:
    """Describes the capabilities of a model.

    Attributes:
        supports_vision: Can process image inputs
        supports_pdf: Can process PDF/document inputs
        supports_audio: Can process audio inputs
        supports_video: Can process video inputs
        supports_image_generation: Can generate images
        supported_modalities: Set of supported modality types
    """

    supports_vision: bool = False
    supports_pdf: bool = False
    supports_audio: bool = False
    supports_video: bool = False
    supports_image_generation: bool = False
    supported_modalities: Set[str] = field(default_factory=lambda: {"text"})


class CapabilityMixin(ABC):
    """Mixin to add capability detection to LLM classes.

    Uses LiteLLM's built-in functions to detect model capabilities.
    Requires that the class has a `model_name` attribute.

    Capabilities are cached after first detection to avoid repeated API calls.
    """

    model_name: str  # Expected from BaseLLM
    _capabilities_cache: Optional[ModelCapabilities]  # Instance-level cache

    def get_capabilities(self) -> ModelCapabilities:
        """Detect and return model capabilities (cached).

        Uses LiteLLM's capability detection functions to determine
        what modalities the model supports. Results are cached after
        first call to avoid repeated API calls.

        Returns:
            ModelCapabilities instance with detected capabilities
        """
        # Use getattr to handle the cache as an instance attribute
        # This avoids sharing cache between different model instances
        cache = getattr(self, "_capabilities_cache", None)
        if cache is not None:
            return cache

        self._capabilities_cache = self._detect_capabilities()
        return self._capabilities_cache

    def _detect_capabilities(self) -> ModelCapabilities:
        """Internal method to detect capabilities without caching.

        Returns:
            ModelCapabilities instance with detected capabilities
        """
        caps = ModelCapabilities()

        # Check vision support using LiteLLM
        try:
            caps.supports_vision = litellm.supports_vision(model=self.model_name)
        except Exception:
            caps.supports_vision = False

        # Check audio input support using LiteLLM
        try:
            caps.supports_audio = litellm.supports_audio_input(model=self.model_name)
        except Exception:
            caps.supports_audio = False

        # Build supported modalities set
        if caps.supports_vision:
            caps.supported_modalities.add("image")
            # Vision models can typically also handle PDFs
            caps.supports_pdf = True
            caps.supported_modalities.add("pdf")

        if caps.supports_audio:
            caps.supported_modalities.add("audio")

        # Check for video support (Gemini 1.5+ models)
        # LiteLLM doesn't have supports_video() yet, infer from model name
        if "gemini" in self.model_name.lower():
            if any(v in self.model_name.lower() for v in ["1.5", "2.0", "2.5"]):
                caps.supports_video = True
                caps.supported_modalities.add("video")

        # Check for image generation capability
        # Models with "image" or "dall-e" in the name can generate images
        if any(kw in self.model_name.lower() for kw in ["image", "dall-e", "dalle"]):
            caps.supports_image_generation = True

        return caps

    def clear_capabilities_cache(self) -> None:
        """Clear the cached capabilities.

        Useful if you need to re-detect capabilities after model changes.
        """
        # Setting to None will trigger re-detection on next get_capabilities() call
        self._capabilities_cache = None

    @property
    def supports_vision(self) -> bool:
        """Quick check for vision support.

        Returns:
            True if model supports image inputs
        """
        return self.get_capabilities().supports_vision

    @property
    def supports_pdf(self) -> bool:
        """Quick check for PDF support.

        Returns:
            True if model supports PDF/document inputs
        """
        return self.get_capabilities().supports_pdf

    @property
    def supports_audio(self) -> bool:
        """Quick check for audio support.

        Returns:
            True if model supports audio inputs
        """
        return self.get_capabilities().supports_audio

    @property
    def supports_video(self) -> bool:
        """Quick check for video support.

        Returns:
            True if model supports video inputs
        """
        return self.get_capabilities().supports_video
