"""
Test Configuration Generator Service.

This service handles the generation of test configurations based on user prompts
using LLM and Jinja2 templates.
"""

from pathlib import Path

import jinja2

from rhesis.backend.app.schemas.services import TestConfigResponse
from rhesis.sdk.models.providers.gemini import GeminiLLM


class TestConfigGeneratorService:
    """Service for generating test configurations from user prompts."""

    def __init__(self, max_sample_size: int = 20):
        """Initialize the service with template environment.

        Args:
            max_sample_size: Maximum allowed sample size per category (default: 20)
        """
        self.template_dir = Path(__file__).parent.parent / "templates"
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.template_dir)),
            autoescape=jinja2.select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.llm = GeminiLLM()
        self.max_sample_size = max_sample_size

    def generate_config(self, prompt: str, sample_size: int = 5) -> TestConfigResponse:
        """
        Generate test configuration based on user prompt.

        Args:
            prompt: User description of what they want to test
            sample_size: Number of items to generate for each category (default: 5, max: 20)

        Returns:
            TestConfigResponse: Generated test configuration

        Raises:
            ValueError: If prompt is empty or invalid
            RuntimeError: If LLM response cannot be parsed
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        if sample_size < 1:
            raise ValueError("Sample size must be at least 1")
        if sample_size > self.max_sample_size:
            raise ValueError(f"Sample size must be less than {self.max_sample_size}")

        # Render template with user prompt and sample size
        template = self.jinja_env.get_template("test_config_generator.jinja2")
        rendered_prompt = template.render({"prompt": prompt, "sample_size": sample_size})

        # Generate response using LLM
        return self.llm.generate(rendered_prompt, schema=TestConfigResponse)
