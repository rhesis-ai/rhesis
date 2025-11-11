"""
Jinja2 template loader for Penelope prompts.

Provides utilities for loading and rendering Jinja2 templates from files,
with support for custom filters and functions.
"""

from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, Template, select_autoescape


class PromptLoader:
    """
    Jinja2 template loader for prompt templates.

    Manages template loading from the templates/ directory with sensible
    defaults for prompt rendering.

    Example:
        >>> loader = PromptLoader()
        >>> prompt = loader.render_template(
        ...     "goal_evaluation.j2",
        ...     goal="Test authentication",
        ...     conversation="User: Hello\\nAssistant: Hi!"
        ... )
    """

    def __init__(self, template_dir: Optional[Path] = None):
        """
        Initialize the prompt loader.

        Args:
            template_dir: Directory containing .j2 template files.
                Defaults to prompts/templates/ in the package.
        """
        if template_dir is None:
            # Default to templates/ directory in the prompts module
            prompts_dir = Path(__file__).parent
            template_dir = prompts_dir / "templates"

        self.template_dir = template_dir
        self.template_dir.mkdir(parents=True, exist_ok=True)

        # Create Jinja2 environment with sensible defaults
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(enabled_extensions=()),  # No escaping for prompts
            trim_blocks=True,  # Remove first newline after block
            lstrip_blocks=True,  # Strip leading spaces before blocks
            keep_trailing_newline=True,  # Preserve final newline
        )

        # Add custom filters
        self._register_filters()

    def _register_filters(self) -> None:
        """Register custom Jinja2 filters for prompt rendering."""

        # Add a filter to truncate long text
        def truncate_text(text: str, length: int = 100, suffix: str = "...") -> str:
            """Truncate text to specified length."""
            if len(text) <= length:
                return text
            return text[: length - len(suffix)] + suffix

        self.env.filters["truncate_text"] = truncate_text

        # Add a filter to count words
        def word_count(text: str) -> int:
            """Count words in text."""
            return len(text.split())

        self.env.filters["word_count"] = word_count

        # Add a filter to format lists
        def format_list(items: list, bullet: str = "-") -> str:
            """Format list items with bullets."""
            return "\n".join(f"{bullet} {item}" for item in items)

        self.env.filters["format_list"] = format_list

    def load_template(self, template_name: str) -> Template:
        """
        Load a Jinja2 template by name.

        Args:
            template_name: Name of the template file (e.g., "goal_evaluation.j2")

        Returns:
            Jinja2 Template object

        Raises:
            TemplateNotFound: If template file doesn't exist
        """
        return self.env.get_template(template_name)

    def render_template(self, template_name: str, **kwargs: Any) -> str:
        """
        Load and render a template in one step.

        Args:
            template_name: Name of the template file
            **kwargs: Variables to pass to the template

        Returns:
            Rendered prompt string

        Example:
            >>> loader.render_template(
            ...     "system_prompt.j2",
            ...     instructions="Test auth",
            ...     goal="Verify login works"
            ... )
        """
        template = self.load_template(template_name)
        return template.render(**kwargs)

    def render_string(self, template_string: str, **kwargs: Any) -> str:
        """
        Render a template from a string (not a file).

        Useful for inline templates or programmatic template generation.

        Args:
            template_string: Template content as a string
            **kwargs: Variables to pass to the template

        Returns:
            Rendered prompt string

        Example:
            >>> loader.render_string(
            ...     "Hello {{ name }}!",
            ...     name="World"
            ... )
            'Hello World!'
        """
        template = self.env.from_string(template_string)
        return template.render(**kwargs)


# Singleton instance for easy access
_default_loader: Optional[PromptLoader] = None


def get_loader() -> PromptLoader:
    """
    Get the default prompt loader instance.

    Returns:
        Singleton PromptLoader instance
    """
    global _default_loader
    if _default_loader is None:
        _default_loader = PromptLoader()
    return _default_loader


def render_template(template_name: str, **kwargs: Any) -> str:
    """
    Convenience function to render a template using the default loader.

    Args:
        template_name: Name of the template file
        **kwargs: Variables to pass to the template

    Returns:
        Rendered prompt string
    """
    return get_loader().render_template(template_name, **kwargs)
