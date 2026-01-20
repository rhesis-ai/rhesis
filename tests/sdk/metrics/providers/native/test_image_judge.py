"""Tests for ImageJudge metric."""

import base64
from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk.metrics.base import MetricResult, MetricType, ScoreType
from rhesis.sdk.metrics.providers.native.configs import (
    DEFAULT_IMAGE_EVALUATION_PROMPT,
    ImageJudgeConfig,
)
from rhesis.sdk.metrics.providers.native.image_judge import ImageJudge


class TestImageJudgeConfig:
    """Test ImageJudgeConfig class."""

    def test_default_values(self):
        """Test that ImageJudgeConfig has sensible defaults."""
        config = ImageJudgeConfig()

        assert config.categories == ["pass", "partial", "fail"]
        assert config.passing_categories == ["pass"]
        assert config.evaluation_prompt == DEFAULT_IMAGE_EVALUATION_PROMPT

    def test_custom_categories(self):
        """Test ImageJudgeConfig with custom categories."""
        config = ImageJudgeConfig(
            categories=["excellent", "good", "poor"],
            passing_categories=["excellent", "good"],
        )

        assert config.categories == ["excellent", "good", "poor"]
        assert config.passing_categories == ["excellent", "good"]

    def test_custom_evaluation_prompt(self):
        """Test ImageJudgeConfig with custom evaluation prompt."""
        custom_prompt = "Custom evaluation criteria"
        config = ImageJudgeConfig(evaluation_prompt=custom_prompt)

        assert config.evaluation_prompt == custom_prompt


class TestImageJudgeInit:
    """Test ImageJudge initialization."""

    def test_default_initialization(self):
        """Test ImageJudge with default parameters."""
        judge = ImageJudge()

        assert judge.categories == ["pass", "partial", "fail"]
        assert judge.passing_categories == ["pass"]
        assert judge.metric_type == MetricType.GENERATION
        assert judge.score_type == ScoreType.CATEGORICAL
        assert judge.requires_ground_truth is True

    def test_custom_categories(self):
        """Test ImageJudge with custom categories."""
        judge = ImageJudge(
            categories=["excellent", "good", "acceptable", "poor"],
            passing_categories=["excellent", "good"],
        )

        assert judge.categories == ["excellent", "good", "acceptable", "poor"]
        assert judge.passing_categories == ["excellent", "good"]

    def test_custom_model(self):
        """Test ImageJudge with custom model string."""
        judge = ImageJudge(model="gemini/gemini-1.5-flash")

        assert judge.model.model_name == "gemini/gemini-1.5-flash"

    def test_with_name_and_description(self):
        """Test ImageJudge with name and description."""
        judge = ImageJudge(
            name="my_image_judge",
            description="Evaluates generated images",
        )

        assert judge.name == "my_image_judge"
        assert judge.description == "Evaluates generated images"


class TestImageJudgeHelpers:
    """Test ImageJudge helper methods."""

    @pytest.fixture
    def judge(self):
        """Create a basic ImageJudge for testing."""
        return ImageJudge()

    def test_is_image_path_or_url_with_url(self, judge):
        """Test detection of image URLs."""
        assert judge._is_image_path_or_url("https://example.com/image.jpg") is True
        assert judge._is_image_path_or_url("http://example.com/image.png") is True
        assert judge._is_image_path_or_url("data:image/png;base64,abc123") is True

    def test_is_image_path_or_url_with_path(self, judge):
        """Test detection of image file paths."""
        assert judge._is_image_path_or_url("/path/to/image.jpg") is True
        assert judge._is_image_path_or_url("/path/to/image.png") is True
        assert judge._is_image_path_or_url("./image.webp") is True

    def test_is_image_path_or_url_with_text(self, judge):
        """Test that plain text is not detected as image."""
        assert judge._is_image_path_or_url("Generate a sunset image") is False
        assert judge._is_image_path_or_url("A cat sitting on a chair") is False

    def test_is_image_path_or_url_empty(self, judge):
        """Test empty string."""
        assert judge._is_image_path_or_url("") is False

    @patch("rhesis.sdk.models.content.Path")
    def test_load_image_from_url(self, mock_path, judge):
        """Test loading image from URL."""
        from rhesis.sdk.models.content import ImageContent

        image = judge._load_image("https://example.com/image.jpg")

        assert image.url == "https://example.com/image.jpg"
        assert isinstance(image, ImageContent)

    def test_load_image_from_base64(self, judge):
        """Test loading image from base64 data URL."""
        from rhesis.sdk.models.content import ImageContent

        original_data = b"fake image data"
        b64_data = base64.b64encode(original_data).decode("utf-8")
        data_url = f"data:image/png;base64,{b64_data}"

        image = judge._load_image(data_url)

        assert image.data == original_data
        assert isinstance(image, ImageContent)

    def test_evaluate_score(self, judge):
        """Test score evaluation."""
        assert judge._evaluate_score("pass", ["pass"]) is True
        assert judge._evaluate_score("partial", ["pass"]) is False
        assert judge._evaluate_score("fail", ["pass"]) is False
        assert judge._evaluate_score("partial", ["pass", "partial"]) is True


class TestImageJudgeEvaluate:
    """Test ImageJudge evaluate method."""

    @pytest.fixture
    def mock_model(self):
        """Create a mock model."""
        model = MagicMock()
        model.model_name = "mock/model"
        model.generate_multimodal = MagicMock(
            return_value='{"score": "pass", "reason": "Image matches expected description"}'
        )
        return model

    @pytest.fixture
    def judge_with_mock(self, mock_model):
        """Create ImageJudge with mocked model."""
        judge = ImageJudge()
        judge.model = mock_model
        return judge

    @patch.object(ImageJudge, "_load_image")
    def test_evaluate_generation_mode(self, mock_load_image, judge_with_mock):
        """Test evaluate in generation mode (text input -> image output)."""
        # Setup mock image
        mock_image = MagicMock()
        mock_load_image.return_value = mock_image

        result = judge_with_mock.evaluate(
            input="Generate a sunset landscape",
            output="/path/to/generated.png",
            expected_output="Orange sky with mountains",
        )

        assert isinstance(result, MetricResult)
        assert result.score == "pass"
        assert "reason" in result.details
        assert result.details["is_transformation_mode"] is False

    @patch.object(ImageJudge, "_load_image")
    def test_evaluate_transformation_mode(self, mock_load_image, judge_with_mock):
        """Test evaluate in transformation mode (image -> image)."""
        # Setup mock images
        mock_image = MagicMock()
        mock_load_image.return_value = mock_image

        result = judge_with_mock.evaluate(
            input="/path/to/source.png",  # Image path triggers transformation mode
            output="/path/to/transformed.png",
            expected_output="Grayscale version of the input",
        )

        assert isinstance(result, MetricResult)
        assert result.score == "pass"
        assert result.details["is_transformation_mode"] is True

    @patch.object(ImageJudge, "_load_image")
    def test_evaluate_with_context(self, mock_load_image, judge_with_mock):
        """Test evaluate with context provided."""
        mock_image = MagicMock()
        mock_load_image.return_value = mock_image

        result = judge_with_mock.evaluate(
            input="Generate landscape",
            output="/path/to/image.png",
            expected_output="Mountain scene",
            context=["Style: realistic", "Time: sunset"],
        )

        assert isinstance(result, MetricResult)
        # Verify generate_multimodal was called
        judge_with_mock.model.generate_multimodal.assert_called_once()

    def test_evaluate_missing_expected_output(self, judge_with_mock):
        """Test that evaluate raises error when expected_output is missing."""
        with pytest.raises(ValueError, match="requires expected_output"):
            judge_with_mock.evaluate(
                input="Generate image",
                output="/path/to/image.png",
                expected_output=None,
            )

    @patch.object(ImageJudge, "_load_image")
    def test_evaluate_handles_partial_score(self, mock_load_image):
        """Test evaluate correctly handles partial score."""
        mock_model = MagicMock()
        mock_model.model_name = "mock/model"
        mock_model.generate_multimodal = MagicMock(
            return_value='{"score": "partial", "reason": "Some elements missing"}'
        )

        mock_image = MagicMock()
        mock_load_image.return_value = mock_image

        judge = ImageJudge()
        judge.model = mock_model

        result = judge.evaluate(
            input="Generate sunset",
            output="/path/to/image.png",
            expected_output="Sunset with clouds",
        )

        assert result.score == "partial"
        assert result.details["is_successful"] is False

    @patch.object(ImageJudge, "_load_image")
    def test_evaluate_handles_fail_score(self, mock_load_image):
        """Test evaluate correctly handles fail score."""
        mock_model = MagicMock()
        mock_model.model_name = "mock/model"
        mock_model.generate_multimodal = MagicMock(
            return_value='{"score": "fail", "reason": "Image does not match"}'
        )

        mock_image = MagicMock()
        mock_load_image.return_value = mock_image

        judge = ImageJudge()
        judge.model = mock_model

        result = judge.evaluate(
            input="Generate cat",
            output="/path/to/image.png",
            expected_output="A cat sitting",
        )

        assert result.score == "fail"
        assert result.details["is_successful"] is False

    @patch.object(ImageJudge, "_load_image")
    def test_evaluate_handles_non_json_response(self, mock_load_image):
        """Test evaluate fallback when model doesn't return valid JSON."""
        mock_model = MagicMock()
        mock_model.model_name = "mock/model"
        # Return plain text instead of JSON
        mock_model.generate_multimodal = MagicMock(
            return_value="The image shows a pass quality result because it matches well."
        )

        mock_image = MagicMock()
        mock_load_image.return_value = mock_image

        judge = ImageJudge()
        judge.model = mock_model

        result = judge.evaluate(
            input="Generate sunset",
            output="/path/to/image.png",
            expected_output="A sunset",
        )

        # Should extract "pass" from the text
        assert result.score == "pass"


class TestImageJudgeFromDict:
    """Test ImageJudge.from_dict method."""

    def test_from_dict_basic(self):
        """Test creating ImageJudge from dictionary."""
        config = {
            "categories": ["good", "bad"],
            "passing_categories": ["good"],
            "name": "test_judge",
        }

        judge = ImageJudge.from_dict(config)

        assert judge.categories == ["good", "bad"]
        assert judge.passing_categories == ["good"]
        assert judge.name == "test_judge"

    def test_from_dict_with_extra_keys(self):
        """Test that from_dict ignores unknown keys."""
        config = {
            "categories": ["pass", "fail"],
            "passing_categories": ["pass"],
            "unknown_key": "should be ignored",
        }

        judge = ImageJudge.from_dict(config)

        assert judge.categories == ["pass", "fail"]


class TestImageJudgeFactory:
    """Test ImageJudge creation via factory."""

    def test_create_via_factory(self):
        """Test creating ImageJudge through MetricFactory."""
        from rhesis.sdk.metrics import MetricFactory

        judge = MetricFactory.create(
            "rhesis",
            "ImageJudge",
            categories=["pass", "fail"],
            passing_categories=["pass"],
        )

        assert isinstance(judge, ImageJudge)
        assert judge.categories == ["pass", "fail"]

    def test_create_via_factory_with_defaults(self):
        """Test creating ImageJudge through factory with defaults."""
        from rhesis.sdk.metrics import MetricFactory

        judge = MetricFactory.create("rhesis", "ImageJudge")

        assert isinstance(judge, ImageJudge)
        assert judge.categories == ["pass", "partial", "fail"]
        assert judge.passing_categories == ["pass"]
