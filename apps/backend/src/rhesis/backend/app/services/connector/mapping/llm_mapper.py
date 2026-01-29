"""LLM-based mapping generation service."""

import os
from typing import Any, Dict

from jinja2 import Template
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.llm_utils import get_user_generation_model
from rhesis.backend.logging import logger
from rhesis.sdk.models.factory import get_model


class MappingGenerationOutput(BaseModel):
    """Structured output schema for LLM mapping generation."""

    request_mapping: Dict[str, Any] = Field(
        description=(
            'Function parameter mappings using Jinja2 syntax: {"param": "{{ standard_field }}"}'
        )
    )
    response_mapping: Dict[str, Any] = Field(
        description=(
            'Output field mappings using JSONPath/Jinja2: {"standard_field": "$.output.path"}'
        )
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score 0.0-1.0 for these mappings",
    )
    reasoning: str = Field(
        description="Brief explanation of mapping choices and any assumptions made"
    )


class LLMMapper:
    """LLM-based mapping generation using user's generation model with Pydantic schema."""

    def __init__(self):
        """Initialize LLM mapper and load prompt template."""
        # Load prompt template
        template_path = os.path.join(os.path.dirname(__file__), "mapping_generation.jinja")
        with open(template_path, "r") as f:
            self.prompt_template = Template(f.read())

    def generate_mappings(
        self,
        db: Session,
        user: User,
        function_name: str,
        parameters: Dict[str, Any],
        return_type: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """
        Generate mappings using LLM with structured Pydantic output.

        Uses user's configured generation model from settings.

        Args:
            db: Database session
            user: User for model access
            function_name: Name of the function
            parameters: Function parameters
            return_type: Function return type
            description: Function description

        Returns:
            {
                "request_mapping": {...},
                "response_mapping": {...},
                "confidence": float,
                "reasoning": str
            }
        """
        logger.info(f"Generating mappings with LLM for function: {function_name}")

        try:
            # Get user's generation model (can be string or BaseLLM instance)
            model_or_provider = get_user_generation_model(db, user)

            # If it's a string (provider name), convert to model instance
            if isinstance(model_or_provider, str):
                logger.debug(f"Converting provider '{model_or_provider}' to model instance")
                model = get_model(provider=model_or_provider)
            else:
                model = model_or_provider

            # Render prompt with function details
            prompt = self.prompt_template.render(
                function_name=function_name,
                parameters=parameters,
                return_type=return_type,
                description=description,
            )

            # Call LLM with Pydantic schema for structured output
            response = model.generate(
                prompt=prompt,
                schema=MappingGenerationOutput,  # SDK models use 'schema', not 'response_format'
                temperature=0.1,  # Low temperature for consistent mappings
            )

            # Handle response - could be dict or Pydantic model
            if isinstance(response, dict):
                result = response
            else:
                result = response.model_dump() if hasattr(response, "model_dump") else response

            logger.info(
                f"LLM generated mappings for {function_name} "
                f"with confidence: {result['confidence']:.2f}"
            )
            logger.debug(f"LLM reasoning: {result['reasoning']}")

            return result

        except Exception as e:
            logger.error(f"LLM mapping generation failed for {function_name}: {e}", exc_info=True)
            # Return minimal fallback mappings
            return {
                "request_mapping": {"input": "{{ input }}"},
                "response_mapping": {"output": "{{ response or result }}"},
                "confidence": 0.3,
                "reasoning": f"LLM generation failed: {e}. Using minimal fallback.",
            }
