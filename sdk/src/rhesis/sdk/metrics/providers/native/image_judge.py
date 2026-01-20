"""Image evaluation metric using vision-capable LLMs.

This module provides the ImageJudge class for evaluating images against
expected descriptions using multimodal models like Gemini.
"""

from dataclasses import fields
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import create_model

from rhesis.sdk.metrics.base import MetricResult, MetricScope, MetricType, ScoreType
from rhesis.sdk.metrics.providers.native.base import JudgeBase
from rhesis.sdk.metrics.providers.native.configs import ImageJudgeConfig
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.content import ImageContent, Message, TextContent

METRIC_TYPE = MetricType.GENERATION
SCORE_TYPE = ScoreType.CATEGORICAL


class ImageJudge(JudgeBase):
    """
    A metric that evaluates images against expected descriptions using vision-capable LLMs.

    ImageJudge supports two evaluation modes:
    1. Generation mode: Evaluates a generated image against an expected description
       (input is the generation prompt, output is the image)
    2. Transformation mode: Evaluates an image transformation
       (input is the source image path/URL, output is the transformed image)

    The metric uses categorical scoring (default: pass/partial/fail) and returns
    detailed reasoning about why the image does or doesn't match expectations.

    Requires a vision-capable model (e.g., gemini/gemini-1.5-flash, openai/gpt-4-vision).

    Example:
        >>> judge = ImageJudge(model="gemini/gemini-1.5-flash")
        >>> result = judge.evaluate(
        ...     input="A sunset over mountains",
        ...     output="path/to/generated_image.png",
        ...     expected_output="Orange/red sky with mountain silhouettes"
        ... )
        >>> print(result.score)  # "pass", "partial", or "fail"
        >>> print(result.details["reason"])
    """

    # Common image file extensions
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}

    def __init__(
        self,
        categories: Optional[List[str]] = None,
        passing_categories: Optional[Union[str, List[str]]] = None,
        evaluation_prompt: Optional[str] = None,
        evaluation_steps: Optional[str] = None,
        reasoning: Optional[str] = None,
        evaluation_examples: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        model: Optional[Union[BaseLLM, str]] = None,
        requires_ground_truth: bool = True,
        requires_context: bool = False,
        metric_scope: Optional[List[Union[str, "MetricScope"]]] = None,
    ):
        """
        Initialize the ImageJudge metric.

        Args:
            categories: Valid score categories (default: ["pass", "partial", "fail"])
            passing_categories: Categories considered successful (default: ["pass"])
            evaluation_prompt: Main evaluation criteria. If None, uses default image
                analysis prompt optimized for visual evaluation.
            evaluation_steps: Step-by-step evaluation process
            reasoning: Guidelines for the LLM's reasoning process
            evaluation_examples: Examples to guide evaluation
            name: Unique name for this metric instance
            description: Human-readable description of what this metric evaluates
            model: Vision-capable LLM model to use (e.g., "gemini/gemini-1.5-flash")
            requires_ground_truth: Whether expected_output is required (default: True)
            requires_context: Whether context is required (default: False)
            metric_scope: Scopes where this metric applies

        Note:
            The model must support vision/multimodal inputs. Models like
            gemini-1.5-flash, gemini-1.5-pro, gpt-4-vision, claude-3-* support vision.
        """
        if metric_scope is None:
            metric_scope = [MetricScope.IMAGE]

        self.config = ImageJudgeConfig(
            categories=categories,
            passing_categories=passing_categories,
            evaluation_prompt=evaluation_prompt,
            evaluation_steps=evaluation_steps,
            reasoning=reasoning,
            evaluation_examples=evaluation_examples,
            name=name,
            description=description,
            score_type=SCORE_TYPE,
            metric_type=METRIC_TYPE,
            requires_ground_truth=requires_ground_truth,
            requires_context=requires_context,
            metric_scope=metric_scope,
            class_name=self.__class__.__name__,
        )

        super().__init__(config=self.config, model=model)

        self.categories = self.config.categories
        self.passing_categories = self.config.passing_categories

        # Set up Jinja environment for template rendering
        self._setup_jinja_environment()

    def _is_image_path_or_url(self, value: str) -> bool:
        """
        Determine if a string represents an image path or URL.

        Args:
            value: String to check

        Returns:
            True if the value appears to be an image path or URL
        """
        if not value:
            return False

        # Check for URL patterns
        if value.startswith(("http://", "https://", "data:image/")):
            return True

        # Check for file path with image extension
        try:
            path = Path(value)
            if path.suffix.lower() in self.IMAGE_EXTENSIONS:
                return True
            # Also check if it's an existing file
            if path.exists() and path.is_file():
                return path.suffix.lower() in self.IMAGE_EXTENSIONS
        except (OSError, ValueError):
            pass

        return False

    def _load_image(
        self, image_source: Union[str, bytes], mime_type: str = "image/png"
    ) -> ImageContent:
        """
        Load an image from various sources.

        Args:
            image_source: Path, URL, base64 data URL, or raw bytes
            mime_type: MIME type for bytes input (default: "image/png")

        Returns:
            ImageContent instance

        Raises:
            ValueError: If the image cannot be loaded
        """
        if isinstance(image_source, bytes):
            # Raw bytes
            return ImageContent.from_bytes(image_source, mime_type=mime_type)
        elif image_source.startswith("data:image/"):
            # Base64 data URL
            return ImageContent.from_base64(image_source)
        elif image_source.startswith(("http://", "https://")):
            # URL
            return ImageContent.from_url(image_source)
        else:
            # Local file path
            path = Path(image_source)
            if not path.exists():
                raise ValueError(f"Image file not found: {image_source}")
            return ImageContent.from_file(path)

    def _get_prompt_template(
        self,
        input: str,
        output: str,
        expected_output: str,
        context: Optional[List[str]] = None,
        is_transformation_mode: bool = False,
        **additional_template_vars,
    ) -> str:
        """
        Generate the evaluation prompt using the Jinja template.

        Args:
            input: The generation prompt or input image description
            output: Description placeholder (actual image sent separately)
            expected_output: Text description of expected image content
            context: Optional context information
            is_transformation_mode: Whether evaluating a transformation

        Returns:
            Rendered prompt string
        """
        try:
            context_text = "\n".join(context) if context else "No context provided."
        except (TypeError, AttributeError) as e:
            raise ValueError(f"Invalid context format: {e}") from e

        try:
            template = self.jinja_env.get_template("image_metric.jinja")
        except Exception as e:
            raise ValueError(f"Failed to load template: {e}") from e

        template_vars = {
            "evaluation_prompt": self.evaluation_prompt,
            "evaluation_steps": self.evaluation_steps,
            "reasoning": self.reasoning,
            "evaluation_examples": self.evaluation_examples,
            "input": input,
            "context_text": context_text,
            "expected_output": expected_output,
            "is_transformation_mode": is_transformation_mode,
            "categories": self.categories,
            "passing_categories": self.passing_categories,
            "score_type": self.score_type.value if self.score_type else "categorical",
        }
        template_vars.update(additional_template_vars)

        try:
            return template.render(**template_vars)
        except Exception as e:
            raise ValueError(f"Failed to render template: {e}") from e

    def evaluate(
        self,
        input: str,
        output: Union[str, bytes],
        expected_output: Optional[str],
        context: Optional[List[str]] = None,
        output_mime_type: str = "image/png",
    ) -> MetricResult:
        """
        Evaluate an image against expected description.

        This method supports two modes:
        1. Generation mode: `input` is a text prompt, `output` is the generated image
        2. Transformation mode: `input` is an input image path/URL, `output` is the result

        Args:
            input: The generation prompt OR input image path/URL for transformations
            output: Path, URL, base64 data URL, or raw bytes of the image to evaluate
            expected_output: Text description of what the output image should contain
            context: Optional additional context for evaluation
            output_mime_type: MIME type when output is bytes (default: "image/png")

        Returns:
            MetricResult with:
                - score: Categorical score (e.g., "pass", "partial", "fail")
                - details: Dict containing reason, is_successful, prompt, etc.

        Raises:
            ValueError: If output image cannot be loaded
            ValueError: If expected_output is None and requires_ground_truth is True
            ValueError: If the model doesn't support vision

        Example:
            >>> # Generation mode with file path
            >>> result = judge.evaluate(
            ...     input="Create a sunset landscape",
            ...     output="path/to/image.png",
            ...     expected_output="Orange sky with mountains"
            ... )

            >>> # Generation mode with bytes
            >>> result = judge.evaluate(
            ...     input="Create a sunset landscape",
            ...     output=image_bytes,
            ...     expected_output="Orange sky with mountains",
            ...     output_mime_type="image/png"
            ... )

            >>> # Transformation mode
            >>> result = judge.evaluate(
            ...     input="path/to/source.png",
            ...     output="path/to/transformed.png",
            ...     expected_output="Grayscale version of the input"
            ... )
        """
        # Validate expected_output if required
        if expected_output is None and self.requires_ground_truth:
            raise ValueError(
                f"{self.name or 'ImageJudge'} metric requires expected_output but none was provided"
            )

        # Determine evaluation mode
        is_transformation_mode = self._is_image_path_or_url(input)

        # Load the output image (required)
        try:
            output_image = self._load_image(output, mime_type=output_mime_type)
        except Exception as e:
            raise ValueError(f"Failed to load output image: {e}") from e

        # Load input image if in transformation mode
        input_image = None
        if is_transformation_mode:
            try:
                input_image = self._load_image(input)
            except Exception as e:
                raise ValueError(f"Failed to load input image: {e}") from e

        # Generate the evaluation prompt
        prompt = self._get_prompt_template(
            input=input if not is_transformation_mode else "See input image below",
            output="See image below",
            expected_output=expected_output or "",
            context=context,
            is_transformation_mode=is_transformation_mode,
        )

        # Initialize details
        details = self._get_base_details(prompt)
        details.update(
            {
                "categories": self.categories,
                "passing_categories": self.passing_categories,
                "is_transformation_mode": is_transformation_mode,
            }
        )

        try:
            # Build multimodal content for the vision model
            content_parts: List[Any] = [TextContent(text=prompt)]

            if is_transformation_mode and input_image:
                content_parts.append(TextContent(text="\n\n**Input Image:**"))
                content_parts.append(input_image)

            content_parts.append(TextContent(text="\n\n**Output Image to Evaluate:**"))
            content_parts.append(output_image)

            # Create the message for multimodal generation
            message = Message(role="user", content=content_parts)

            # Create response schema for structured output
            if len(self.categories) == 1:
                score_literal = Literal[self.categories[0]]  # type: ignore[valid-type]
            else:
                score_literal = Literal[tuple(self.categories)]  # type: ignore[valid-type]

            ScoreResponse = create_model(
                "ImageScoreResponse",
                score=(score_literal, ...),
                reason=(str, ...),
            )

            # Call the model with multimodal content
            # We need to use generate_multimodal for image inputs
            raw_response = self.model.generate_multimodal([message])

            # Parse the response - it should be JSON
            import json

            try:
                response_data = json.loads(raw_response)
                response = ScoreResponse(**response_data)
            except (json.JSONDecodeError, Exception):
                # If response isn't valid JSON, try to extract score from text
                # This is a fallback for models that don't return structured JSON
                response_text = raw_response.lower()
                detected_score = None
                for category in self.categories:
                    if category.lower() in response_text:
                        detected_score = category
                        break

                if detected_score is None:
                    detected_score = self.categories[-1]  # Default to last (usually worst)

                response = ScoreResponse(score=detected_score, reason=raw_response)

            score = response.score
            reason = response.reason

            # Evaluate success
            is_successful = self._evaluate_score(
                score=score, passing_categories=self.passing_categories
            )

            details.update(
                {
                    "score": score,
                    "reason": reason,
                    "is_successful": is_successful,
                }
            )

            return MetricResult(score=score, details=details)

        except Exception as e:
            return self._handle_evaluation_error(e, details, "error")

    def _evaluate_score(self, score: str, passing_categories: List[str]) -> bool:
        """
        Evaluate if a score meets success criteria.

        Args:
            score: The score to evaluate
            passing_categories: Categories considered passing

        Returns:
            True if score is in passing_categories
        """
        return score in passing_categories

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "ImageJudge":
        """Create an ImageJudge from a dictionary configuration."""
        valid_fields = {field.name for field in fields(ImageJudgeConfig)}
        filtered_config = {k: v for k, v in config.items() if k in valid_fields}
        return cls(**filtered_config)
