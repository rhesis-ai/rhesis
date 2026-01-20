"""Tests for model capability detection."""

from unittest.mock import patch

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.capabilities import CapabilityMixin, ModelCapabilities


class TestModelCapabilities:
    """Test ModelCapabilities dataclass."""

    def test_default_values(self):
        """Test default capability values."""
        caps = ModelCapabilities()

        assert caps.supports_vision is False
        assert caps.supports_pdf is False
        assert caps.supports_audio is False
        assert caps.supports_video is False
        assert caps.supports_image_generation is False
        assert caps.supported_modalities == {"text"}

    def test_custom_values(self):
        """Test custom capability values."""
        caps = ModelCapabilities(
            supports_vision=True, supports_pdf=True, supported_modalities={"text", "image", "pdf"}
        )

        assert caps.supports_vision is True
        assert caps.supports_pdf is True
        assert "image" in caps.supported_modalities
        assert "pdf" in caps.supported_modalities

    def test_modalities_default_factory(self):
        """Test that supported_modalities uses default_factory correctly."""
        caps1 = ModelCapabilities()
        caps2 = ModelCapabilities()

        # Modify one
        caps1.supported_modalities.add("image")

        # The other should remain unchanged
        assert "image" not in caps2.supported_modalities


class TestCapabilityMixin:
    """Test CapabilityMixin class."""

    def test_mixin_requires_model_name(self):
        """Test that CapabilityMixin expects model_name attribute."""

        # Create a concrete implementation for testing
        class TestModel(BaseLLM, CapabilityMixin):
            def load_model(self):
                pass

            def generate(self, *args, **kwargs):
                return "test"

        model = TestModel("test-model")
        assert hasattr(model, "model_name")
        assert model.model_name == "test-model"

    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    def test_get_capabilities_vision_model(self, mock_vision):
        """Test capability detection for vision-capable model."""
        mock_vision.return_value = True

        class TestModel(BaseLLM, CapabilityMixin):
            def load_model(self):
                pass

            def generate(self, *args, **kwargs):
                return "test"

        model = TestModel("gpt-4o")
        caps = model.get_capabilities()

        assert caps.supports_vision is True
        # Vision models typically support PDFs too
        assert caps.supports_pdf is True
        assert "image" in caps.supported_modalities
        assert "pdf" in caps.supported_modalities
        assert "text" in caps.supported_modalities
        mock_vision.assert_called_once_with(model="gpt-4o")

    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    def test_get_capabilities_pdf_model(self, mock_vision):
        """Test capability detection for PDF-capable model."""
        mock_vision.return_value = True

        class TestModel(BaseLLM, CapabilityMixin):
            def load_model(self):
                pass

            def generate(self, *args, **kwargs):
                return "test"

        model = TestModel("gemini-2.0-flash")
        caps = model.get_capabilities()

        assert caps.supports_vision is True
        # Vision models typically support PDFs
        assert caps.supports_pdf is True
        assert "image" in caps.supported_modalities
        assert "pdf" in caps.supported_modalities

    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    def test_get_capabilities_text_only_model(self, mock_vision, mock_audio):
        """Test capability detection for text-only model."""
        mock_vision.return_value = False
        mock_audio.return_value = False

        class TestModel(BaseLLM, CapabilityMixin):
            def load_model(self):
                pass

            def generate(self, *args, **kwargs):
                return "test"

        model = TestModel("gpt-3.5-turbo")
        caps = model.get_capabilities()

        assert caps.supports_vision is False
        assert caps.supports_pdf is False
        assert caps.supported_modalities == {"text"}

    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_get_capabilities_gemini_audio_video(self, mock_audio, mock_vision):
        """Test that Gemini models are detected as supporting audio/video."""
        mock_vision.return_value = True
        mock_audio.return_value = True

        class TestModel(BaseLLM, CapabilityMixin):
            def load_model(self):
                pass

            def generate(self, *args, **kwargs):
                return "test"

        model = TestModel("gemini-1.5-pro")
        caps = model.get_capabilities()

        assert caps.supports_audio is True
        assert caps.supports_video is True
        assert "audio" in caps.supported_modalities
        assert "video" in caps.supported_modalities

    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_get_capabilities_image_generation(self, mock_audio, mock_vision):
        """Test detection of image generation capability."""
        mock_vision.return_value = False
        mock_audio.return_value = False

        class TestModel(BaseLLM, CapabilityMixin):
            def load_model(self):
                pass

            def generate(self, *args, **kwargs):
                return "test"

        model = TestModel("dall-e-3")
        caps = model.get_capabilities()

        assert caps.supports_image_generation is True

    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_get_capabilities_handles_exceptions(self, mock_audio, mock_vision):
        """Test that exceptions from LiteLLM are handled gracefully."""
        mock_vision.side_effect = Exception("LiteLLM error")
        mock_audio.side_effect = Exception("LiteLLM error")

        class TestModel(BaseLLM, CapabilityMixin):
            def load_model(self):
                pass

            def generate(self, *args, **kwargs):
                return "test"

        model = TestModel("unknown-model")
        caps = model.get_capabilities()

        # Should default to False when exceptions occur
        assert caps.supports_vision is False
        assert caps.supports_pdf is False

    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_supports_vision_property(self, mock_audio, mock_vision):
        """Test supports_vision convenience property."""
        mock_vision.return_value = True
        mock_audio.return_value = False

        class TestModel(BaseLLM, CapabilityMixin):
            def load_model(self):
                pass

            def generate(self, *args, **kwargs):
                return "test"

        model = TestModel("gpt-4o")

        assert model.supports_vision is True

    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_supports_pdf_property(self, mock_audio, mock_vision):
        """Test supports_pdf convenience property."""
        mock_vision.return_value = True
        mock_audio.return_value = True

        class TestModel(BaseLLM, CapabilityMixin):
            def load_model(self):
                pass

            def generate(self, *args, **kwargs):
                return "test"

        model = TestModel("gemini-2.0-flash")

        assert model.supports_pdf is True

    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_supports_audio_property(self, mock_audio, mock_vision):
        """Test supports_audio convenience property."""
        mock_vision.return_value = True
        mock_audio.return_value = True

        class TestModel(BaseLLM, CapabilityMixin):
            def load_model(self):
                pass

            def generate(self, *args, **kwargs):
                return "test"

        model = TestModel("gemini-2.0-flash")

        assert model.supports_audio is True

    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_supports_video_property(self, mock_audio, mock_vision):
        """Test supports_video convenience property."""
        mock_vision.return_value = True
        mock_audio.return_value = True

        class TestModel(BaseLLM, CapabilityMixin):
            def load_model(self):
                pass

            def generate(self, *args, **kwargs):
                return "test"

        model = TestModel("gemini-1.5-pro")

        assert model.supports_video is True
