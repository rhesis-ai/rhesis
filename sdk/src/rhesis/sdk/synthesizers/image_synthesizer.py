"""A synthesizer that generates images via LLM and creates image tests."""

import base64
from typing import Any, Dict, List, Optional, Union
from urllib.request import urlopen

from tqdm.auto import tqdm

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.enums import TestType
from rhesis.sdk.models import get_model
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.synthesizers.utils import create_test_set


class ImageSynthesizer:
    """Synthesizer that generates images via LLM and creates image tests.

    This synthesizer uses image generation models (like Gemini Imagen, DALL-E, etc.)
    to generate images from text prompts and creates test cases for evaluating
    those images using the ImageJudge metric.

    Example:
        >>> synthesizer = ImageSynthesizer(
        ...     prompt="Generate images of mountain landscapes at sunset",
        ...     model="gemini/imagen-3.0-generate-002",
        ...     expected_output_template="Image should contain mountains with orange/red sunset sky"
        ... )
        >>> test_set = synthesizer.generate(num_tests=5)
        >>> test_set.push()  # Push to backend with images stored in database
    """

    def __init__(
        self,
        prompt: str,
        model: Optional[Union[str, BaseLLM]] = None,
        batch_size: int = 5,
        expected_output_template: Optional[str] = None,
        category: str = "Image Generation",
        topic: str = "Visual Content",
        behavior: str = "Image Quality",
        image_size: str = "1024x1024",
    ):
        """Initialize the ImageSynthesizer.

        Args:
            prompt: The text prompt to generate images from. This will be used
                as both the generation prompt and stored in test metadata.
            model: The image generation model to use. Can be a string model name
                (e.g., "gemini/imagen-3.0-generate-002") or a BaseLLM instance.
                If None, defaults to the configured default model.
            batch_size: Maximum number of images to generate in parallel (default: 5).
            expected_output_template: Optional template describing what the generated
                images should contain. Used by ImageJudge for evaluation.
                If None, defaults to the generation prompt itself.
            category: Category for the generated tests (default: "Image Generation").
            topic: Topic for the generated tests (default: "Visual Content").
            behavior: Behavior for the generated tests (default: "Image Quality").
            image_size: Size of generated images (default: "1024x1024").
        """
        self.prompt = prompt
        self.batch_size = batch_size
        self.expected_output_template = expected_output_template or prompt
        self.category = category
        self.topic = topic
        self.behavior = behavior
        self.image_size = image_size

        # Initialize model
        if isinstance(model, str) or model is None:
            self.model = get_model(model)
        else:
            self.model = model

    def _get_synthesizer_name(self) -> str:
        """Return the name of the synthesizer for metadata."""
        return self.__class__.__name__

    def _fetch_image_bytes(self, url_or_data: str) -> tuple[bytes, str]:
        """Fetch image bytes from URL or decode from base64 data URL.

        Args:
            url_or_data: Either a URL or a data URL (data:image/...;base64,...)

        Returns:
            Tuple of (image_bytes, mime_type)
        """
        if url_or_data.startswith("data:"):
            # Parse data URL: data:image/png;base64,<data>
            parts = url_or_data.split(",", 1)
            if len(parts) == 2:
                header = parts[0]  # data:image/png;base64
                data = parts[1]
                # Extract MIME type
                mime_type = "image/png"  # default
                if ":" in header and ";" in header:
                    mime_type = header.split(":")[1].split(";")[0]
                return base64.b64decode(data), mime_type
            raise ValueError(f"Invalid data URL format: {url_or_data[:50]}...")
        else:
            # Fetch from URL
            with urlopen(url_or_data) as response:
                content_type = response.headers.get("Content-Type", "image/png")
                return response.read(), content_type

    def _generate_single_image(self, variation_prompt: str) -> Dict[str, Any]:
        """Generate a single image and create a test dict.

        Args:
            variation_prompt: The prompt to use for generation

        Returns:
            Dict containing test data with image binary
        """
        # Generate image using the model
        result = self.model.generate_image(
            prompt=variation_prompt,
            n=1,
            size=self.image_size,
        )

        # Handle both single URL and list of URLs
        url_or_data = result[0] if isinstance(result, list) else result

        # Fetch image bytes
        image_bytes, mime_type = self._fetch_image_bytes(url_or_data)

        # Create test dict
        test = {
            "category": self.category,
            "topic": self.topic,
            "behavior": self.behavior,
            "test_type": TestType.IMAGE.value,
            "test_binary": image_bytes,
            "metadata": {
                "binary_mime_type": mime_type,
                "generation_prompt": variation_prompt,
                "expected_output": self.expected_output_template,
                "generated_by": self._get_synthesizer_name(),
                "model": self.model.model_name,
                "image_size": self.image_size,
            },
        }

        return test

    def generate(self, num_tests: int = 5) -> TestSet:
        """Generate image tests with LLM-generated images.

        Args:
            num_tests: Number of image tests to generate (default: 5).

        Returns:
            TestSet containing the generated image tests.

        Example:
            >>> synthesizer = ImageSynthesizer(
            ...     prompt="A serene mountain landscape",
            ...     model="gemini/imagen-3.0-generate-002"
            ... )
            >>> test_set = synthesizer.generate(num_tests=3)
            >>> print(f"Generated {len(test_set.tests)} image tests")
        """
        all_tests: List[Dict[str, Any]] = []

        # Generate images with progress bar
        with tqdm(total=num_tests, desc="Generating images") as pbar:
            for i in range(num_tests):
                try:
                    # Create variation prompt (can be extended to add variation)
                    variation_prompt = f"{self.prompt} (variation {i + 1})"

                    test = self._generate_single_image(variation_prompt)
                    all_tests.append(test)
                    pbar.update(1)
                except Exception as e:
                    print(f"Warning: Failed to generate image {i + 1}: {e}")
                    pbar.update(1)
                    continue

        if not all_tests:
            raise ValueError("Failed to generate any valid image tests")

        # Create TestSet using utility function
        test_set = create_test_set(
            tests=all_tests,
            model=self.model,
            synthesizer_name=self._get_synthesizer_name(),
            batch_size=self.batch_size,
            num_tests=len(all_tests),
            requested_tests=num_tests,
            generation_prompt=self.prompt,
        )

        # Set test set type to Image
        test_set.test_set_type = TestType.IMAGE

        if test_set.name:
            test_set.name = f"{test_set.name} (Image)"

        return test_set
