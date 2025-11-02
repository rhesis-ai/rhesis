"""
Base classes for prompt management.

Provides the foundation for versioned, templated prompts throughout Penelope.
Supports both simple Python string formatting and advanced Jinja2 templates.
"""

from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, Field


class TemplateFormat(str, Enum):
    """Format of the template string."""

    PYTHON = "python"  # Python .format() style: "Hello {name}"
    JINJA2 = "jinja2"  # Jinja2 template: "Hello {{ name }}"
    JINJA2_FILE = "jinja2_file"  # External .j2 file


class PromptTemplate(BaseModel):
    """
    Base class for all prompt templates.

    Provides versioning, metadata, and rendering capabilities for prompts.
    Supports both Python string formatting and Jinja2 templates.

    All prompts in Penelope inherit from this class for consistency.

    Examples:
        Python format:
        >>> template = PromptTemplate(
        ...     version="1.0.0",
        ...     name="example",
        ...     description="An example prompt",
        ...     template="Hello {name}!",
        ...     format=TemplateFormat.PYTHON
        ... )
        >>> template.render(name="World")
        'Hello World!'

        Jinja2 format:
        >>> template = PromptTemplate(
        ...     version="1.0.0",
        ...     name="example",
        ...     description="An example prompt",
        ...     template="Hello {{ name }}!",
        ...     format=TemplateFormat.JINJA2
        ... )
        >>> template.render(name="World")
        'Hello World!'

        Jinja2 file:
        >>> template = PromptTemplate(
        ...     version="1.0.0",
        ...     name="example",
        ...     description="An example prompt",
        ...     template="example.j2",  # File name
        ...     format=TemplateFormat.JINJA2_FILE
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
    template: str = Field(
        description="The prompt text or template file name (for JINJA2_FILE format)"
    )
    format: TemplateFormat = Field(
        default=TemplateFormat.PYTHON,
        description="Template format: python, jinja2, or jinja2_file",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (author, date, changelog, etc.)",
    )

    def render(self, **kwargs: Any) -> str:
        """
        Render the template with provided variables.

        Automatically chooses the appropriate rendering method based on the format.

        Args:
            **kwargs: Variables to substitute into the template

        Returns:
            Rendered prompt string

        Example:
            >>> prompt.render(name="Alice", goal="Test authentication")
            'Hello Alice! Your goal is: Test authentication'
        """
        if self.format == TemplateFormat.PYTHON:
            return self._render_python(**kwargs)
        elif self.format == TemplateFormat.JINJA2:
            return self._render_jinja2(**kwargs)
        elif self.format == TemplateFormat.JINJA2_FILE:
            return self._render_jinja2_file(**kwargs)
        else:
            raise ValueError(f"Unknown template format: {self.format}")

    def _render_python(self, **kwargs: Any) -> str:
        """Render using Python's .format() method."""
        return self.template.format(**kwargs)

    def _render_jinja2(self, **kwargs: Any) -> str:
        """Render using Jinja2 from an inline template string."""
        # Import here to avoid circular dependency
        from rhesis.penelope.prompts.loader import get_loader

        loader = get_loader()
        return loader.render_string(self.template, **kwargs)

    def _render_jinja2_file(self, **kwargs: Any) -> str:
        """Render using Jinja2 from a template file."""
        # Import here to avoid circular dependency
        from rhesis.penelope.prompts.loader import get_loader

        loader = get_loader()
        return loader.render_template(self.template, **kwargs)

    def __str__(self) -> str:
        """String representation shows name and version."""
        return (
            f"PromptTemplate(name='{self.name}', version='{self.version}', "
            f"format='{self.format.value}')"
        )

    class Config:
        """Pydantic configuration."""

        frozen = False  # Allow modification if needed
