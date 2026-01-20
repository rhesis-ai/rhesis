"""Unit tests for ImageSynthesizer."""

import base64
from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk.enums import TestType
from rhesis.sdk.synthesizers.image_synthesizer import ImageSynthesizer


class TestImageSynthesizerInit:
    """Tests for ImageSynthesizer initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        with patch("rhesis.sdk.synthesizers.image_synthesizer.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_get_model.return_value = mock_model

            synthesizer = ImageSynthesizer(prompt="A mountain landscape")

            assert synthesizer.prompt == "A mountain landscape"
            assert synthesizer.batch_size == 5
            assert synthesizer.expected_output_template == "A mountain landscape"
            assert synthesizer.category == "Image Generation"
            assert synthesizer.topic == "Visual Content"
            assert synthesizer.behavior == "Image Quality"
            assert synthesizer.image_size == "1024x1024"
            assert synthesizer.model == mock_model

    def test_init_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        mock_model = MagicMock()

        synthesizer = ImageSynthesizer(
            prompt="A sunset over the ocean",
            model=mock_model,
            batch_size=10,
            expected_output_template="Orange sky with water reflection",
            category="Nature",
            topic="Landscapes",
            behavior="Realism",
            image_size="512x512",
        )

        assert synthesizer.prompt == "A sunset over the ocean"
        assert synthesizer.batch_size == 10
        assert synthesizer.expected_output_template == "Orange sky with water reflection"
        assert synthesizer.category == "Nature"
        assert synthesizer.topic == "Landscapes"
        assert synthesizer.behavior == "Realism"
        assert synthesizer.image_size == "512x512"
        assert synthesizer.model == mock_model

    def test_init_with_string_model(self):
        """Test initialization with a string model name."""
        with patch("rhesis.sdk.synthesizers.image_synthesizer.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_get_model.return_value = mock_model

            synthesizer = ImageSynthesizer(
                prompt="Test prompt",
                model="gemini/imagen-3.0-generate-002",
            )

            mock_get_model.assert_called_once_with("gemini/imagen-3.0-generate-002")
            assert synthesizer.model == mock_model


class TestImageSynthesizerFetchImageBytes:
    """Tests for _fetch_image_bytes method."""

    def test_fetch_from_base64_data_url(self):
        """Test fetching image bytes from base64 data URL."""
        mock_model = MagicMock()
        synthesizer = ImageSynthesizer(prompt="Test", model=mock_model)

        # Create a test base64 image
        test_data = b"fake image data"
        base64_data = base64.b64encode(test_data).decode("utf-8")
        data_url = f"data:image/png;base64,{base64_data}"

        image_bytes, mime_type = synthesizer._fetch_image_bytes(data_url)

        assert image_bytes == test_data
        assert mime_type == "image/png"

    def test_fetch_from_jpeg_data_url(self):
        """Test fetching image bytes from JPEG data URL."""
        mock_model = MagicMock()
        synthesizer = ImageSynthesizer(prompt="Test", model=mock_model)

        test_data = b"fake jpeg data"
        base64_data = base64.b64encode(test_data).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{base64_data}"

        image_bytes, mime_type = synthesizer._fetch_image_bytes(data_url)

        assert image_bytes == test_data
        assert mime_type == "image/jpeg"

    def test_fetch_invalid_data_url_raises_error(self):
        """Test that invalid data URL raises ValueError."""
        mock_model = MagicMock()
        synthesizer = ImageSynthesizer(prompt="Test", model=mock_model)

        with pytest.raises(ValueError, match="Invalid data URL format"):
            synthesizer._fetch_image_bytes("data:invalid")


class TestImageSynthesizerGenerateSingleImage:
    """Tests for _generate_single_image method."""

    def test_generate_single_image_from_base64(self):
        """Test generating a single image from base64 response."""
        mock_model = MagicMock()
        mock_model.model_name = "test/model"

        # Create test base64 image data
        test_image_data = b"fake image bytes"
        base64_data = base64.b64encode(test_image_data).decode("utf-8")
        data_url = f"data:image/png;base64,{base64_data}"

        mock_model.generate_image.return_value = [data_url]

        synthesizer = ImageSynthesizer(
            prompt="A test image",
            model=mock_model,
            expected_output_template="Should show a test",
        )

        test = synthesizer._generate_single_image("A test image (variation 1)")

        assert test["category"] == "Image Generation"
        assert test["topic"] == "Visual Content"
        assert test["behavior"] == "Image Quality"
        assert test["test_type"] == TestType.IMAGE.value
        assert test["test_binary"] == test_image_data
        assert test["metadata"]["binary_mime_type"] == "image/png"
        assert test["metadata"]["generation_prompt"] == "A test image (variation 1)"
        assert test["metadata"]["expected_output"] == "Should show a test"
        assert test["metadata"]["model"] == "test/model"

    def test_generate_single_image_handles_single_url(self):
        """Test generating image when model returns single URL (not list)."""
        mock_model = MagicMock()
        mock_model.model_name = "test/model"

        test_image_data = b"image bytes"
        base64_data = base64.b64encode(test_image_data).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{base64_data}"

        # Return single string instead of list
        mock_model.generate_image.return_value = data_url

        synthesizer = ImageSynthesizer(prompt="Test", model=mock_model)

        test = synthesizer._generate_single_image("Test prompt")

        assert test["test_binary"] == test_image_data
        assert test["metadata"]["binary_mime_type"] == "image/jpeg"


class TestImageSynthesizerGenerate:
    """Tests for generate method."""

    def test_generate_creates_test_set(self):
        """Test that generate creates a valid TestSet."""
        mock_model = MagicMock()
        mock_model.model_name = "test/model"

        # Create test images
        test_image_data = b"image data"
        base64_data = base64.b64encode(test_image_data).decode("utf-8")
        data_url = f"data:image/png;base64,{base64_data}"

        mock_model.generate_image.return_value = [data_url]

        synthesizer = ImageSynthesizer(
            prompt="Mountain landscape",
            model=mock_model,
        )

        with patch(
            "rhesis.sdk.synthesizers.image_synthesizer.create_test_set"
        ) as mock_create_test_set:
            mock_test_set = MagicMock()
            mock_test_set.name = "Test Set"
            mock_create_test_set.return_value = mock_test_set

            synthesizer.generate(num_tests=3)

            # Verify create_test_set was called
            mock_create_test_set.assert_called_once()
            call_args = mock_create_test_set.call_args

            # Check tests were passed
            tests = call_args.kwargs.get("tests") or call_args.args[0]
            assert len(tests) == 3

            # Check test set type was set
            assert mock_test_set.test_set_type == TestType.IMAGE
            assert mock_test_set.name == "Test Set (Image)"

    def test_generate_handles_errors_gracefully(self):
        """Test that generate continues when some images fail."""
        mock_model = MagicMock()
        mock_model.model_name = "test/model"

        test_image_data = b"image data"
        base64_data = base64.b64encode(test_image_data).decode("utf-8")
        data_url = f"data:image/png;base64,{base64_data}"

        # First call succeeds, second fails, third succeeds
        mock_model.generate_image.side_effect = [
            [data_url],
            Exception("API error"),
            [data_url],
        ]

        synthesizer = ImageSynthesizer(prompt="Test", model=mock_model)

        with patch(
            "rhesis.sdk.synthesizers.image_synthesizer.create_test_set"
        ) as mock_create_test_set:
            mock_test_set = MagicMock()
            mock_test_set.name = "Test Set"
            mock_create_test_set.return_value = mock_test_set

            synthesizer.generate(num_tests=3)

            # Should have 2 successful tests
            call_args = mock_create_test_set.call_args
            tests = call_args.kwargs.get("tests") or call_args.args[0]
            assert len(tests) == 2

    def test_generate_raises_when_all_fail(self):
        """Test that generate raises error when all images fail."""
        mock_model = MagicMock()
        mock_model.model_name = "test/model"
        mock_model.generate_image.side_effect = Exception("API error")

        synthesizer = ImageSynthesizer(prompt="Test", model=mock_model)

        with pytest.raises(ValueError, match="Failed to generate any valid image tests"):
            synthesizer.generate(num_tests=3)

    def test_generate_with_custom_metadata(self):
        """Test that generated tests have correct metadata."""
        mock_model = MagicMock()
        mock_model.model_name = "gemini/imagen-3.0"

        test_image_data = b"test image"
        base64_data = base64.b64encode(test_image_data).decode("utf-8")
        data_url = f"data:image/webp;base64,{base64_data}"

        mock_model.generate_image.return_value = [data_url]

        synthesizer = ImageSynthesizer(
            prompt="A beautiful sunset",
            model=mock_model,
            expected_output_template="Orange sky with sun",
            category="Nature",
            topic="Sunsets",
            behavior="Color Accuracy",
            image_size="512x512",
        )

        with patch(
            "rhesis.sdk.synthesizers.image_synthesizer.create_test_set"
        ) as mock_create_test_set:
            mock_test_set = MagicMock()
            mock_test_set.name = None
            mock_create_test_set.return_value = mock_test_set

            synthesizer.generate(num_tests=1)

            call_args = mock_create_test_set.call_args
            tests = call_args.kwargs.get("tests") or call_args.args[0]
            test = tests[0]

            assert test["category"] == "Nature"
            assert test["topic"] == "Sunsets"
            assert test["behavior"] == "Color Accuracy"
            assert test["metadata"]["expected_output"] == "Orange sky with sun"
            assert test["metadata"]["model"] == "gemini/imagen-3.0"
            assert test["metadata"]["image_size"] == "512x512"


class TestImageSynthesizerIntegration:
    """Integration tests for ImageSynthesizer with Test entity."""

    def test_test_binary_serialization_with_alias(self):
        """Test that test_binary is properly serialized with alias for API transport."""
        from rhesis.sdk.entities.test import Test

        test_data = b"test image bytes"

        test = Test(
            category="Test",
            topic="Test",
            behavior="Test",
            test_binary=test_data,
            metadata={"binary_mime_type": "image/png"},
        )

        # Serialize for API with by_alias=True (as TestSet.push() does)
        data = test.model_dump(by_alias=True, exclude_none=True)

        # test_binary should be renamed to test_binary_base64 and base64 encoded
        assert "test_binary" not in data
        assert "test_binary_base64" in data
        assert data["test_binary_base64"] == base64.b64encode(test_data).decode("utf-8")

    def test_test_binary_none_not_serialized(self):
        """Test that None test_binary is not included in serialization."""
        from rhesis.sdk.entities.test import Test

        test = Test(
            category="Test",
            topic="Test",
            behavior="Test",
            test_binary=None,
        )

        data = test.model_dump(by_alias=True, exclude_none=True)

        # Neither should be in the output when excluding None values
        assert "test_binary" not in data
        assert "test_binary_base64" not in data

    def test_test_binary_nested_in_testset(self):
        """Test that test_binary is properly serialized when nested in TestSet."""
        from rhesis.sdk.entities.test import Test
        from rhesis.sdk.entities.test_set import TestSet

        test_data = b"test image bytes"

        test = Test(
            category="Test",
            topic="Test",
            behavior="Test",
            test_binary=test_data,
            metadata={"binary_mime_type": "image/png"},
        )

        test_set = TestSet(
            name="Image Test Set",
            description="Test set with image tests",
            short_description="Image tests",
            tests=[test],
        )

        # Serialize as TestSet.push() does
        data = test_set.model_dump(mode="json", exclude_none=True, by_alias=True)

        # Nested test should have test_binary_base64, not test_binary
        assert len(data["tests"]) == 1
        nested_test = data["tests"][0]
        assert "test_binary" not in nested_test
        assert "test_binary_base64" in nested_test
        assert nested_test["test_binary_base64"] == base64.b64encode(test_data).decode("utf-8")
