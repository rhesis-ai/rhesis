"""
Base classes for prompt management.

Provides the foundation for versioned, templated prompts throughout Penelope.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class PromptTemplate(BaseModel):
    """
    Base class for all prompt templates.

    Provides versioning, metadata, and rendering capabilities for prompts.
    All prompts in Penelope inherit from this class for consistency.

    Example:
        >>> template = PromptTemplate(
        ...     version="1.0.0",
        ...     name="example",
        ...     description="An example prompt",
        ...     template="Hello {name}!"
        ... )
        >>> template.render(name="World")
        'Hello World!'
    """

    version: str = Field(
        default="1.0.0",
        description="Semantic version of this prompt (major.minor.patch)",
    )
    name: str = Field(description="Unique identifier for this prompt")
    description: str = Field(description="Human-readable description of prompt purpose")
    template: str = Field(description="The prompt text, with optional {placeholders}")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (author, date, changelog, etc.)",
    )

    def render(self, **kwargs: Any) -> str:
        """
        Render the template with provided variables.

        Args:
            **kwargs: Variables to substitute into the template

        Returns:
            Rendered prompt string

        Example:
            >>> prompt.render(name="Alice", goal="Test authentication")
            'Hello Alice! Your goal is: Test authentication'
        """
        return self.template.format(**kwargs)

    def __str__(self) -> str:
        """String representation shows name and version."""
        return f"PromptTemplate(name='{self.name}', version='{self.version}')"

    class Config:
        """Pydantic configuration."""

        frozen = False  # Allow modification if needed

