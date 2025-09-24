"""
Test Configuration Generator Service.

This service handles the generation of test configurations based on user prompts
using LLM and Jinja2 templates.
"""

import json
from pathlib import Path
from typing import Any, Dict

import jinja2

from rhesis.backend.app.schemas.services import TestConfigResponse
from rhesis.sdk.models.providers.gemini import GeminiLLM


class TestConfigGeneratorService:
    """Service for generating test configurations from user prompts."""

    def __init__(self):
        """Initialize the service with template environment."""
        self.template_dir = Path(__file__).parent.parent / "templates"
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.template_dir)),
            autoescape=jinja2.select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.llm = GeminiLLM()

    def generate_config(self, prompt: str) -> TestConfigResponse:
        """
        Generate test configuration based on user prompt.

        Args:
            prompt: User description of what they want to test

        Returns:
            TestConfigResponse: Generated test configuration

        Raises:
            ValueError: If prompt is empty or invalid
            RuntimeError: If LLM response cannot be parsed
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        # Render template with user prompt
        template = self.jinja_env.get_template("test_config_generation.jinja2")
        rendered_prompt = template.render({"prompt": prompt})

        # Generate response using LLM
        response = self.llm.generate(rendered_prompt)

        # Parse and validate response
        parsed_response = self._parse_llm_response(response)

        return TestConfigResponse(
            behaviors=parsed_response.get("behaviors", []),
            topics=parsed_response.get("topics", []),
            test_categories=parsed_response.get("test_categories", []),
            test_scenarios=parsed_response.get("test_scenarios", []),
        )

    def _parse_llm_response(self, response: Any) -> Dict[str, Any]:
        """
        Parse LLM response and extract JSON data.

        Args:
            response: Raw response from LLM

        Returns:
            Dict containing parsed JSON data

        Raises:
            RuntimeError: If response cannot be parsed as JSON
        """
        try:
            if isinstance(response, str):
                # Remove markdown code blocks if present
                cleaned_response = response.strip()
                if cleaned_response.startswith("```json"):
                    cleaned_response = cleaned_response[7:]  # Remove ```json
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-3]  # Remove ```
                cleaned_response = cleaned_response.strip()

                return json.loads(cleaned_response)
            else:
                return response
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse LLM response as JSON: {e}. Response: {response}")
