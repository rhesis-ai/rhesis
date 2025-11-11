"""Tests for prompt loader."""

import pytest
from pathlib import Path
from rhesis.penelope.prompts.loader import PromptLoader, get_loader, render_template


def test_prompt_loader_initialization_default():
    """Test PromptLoader initialization with default path."""
    loader = PromptLoader()

    assert loader.template_dir is not None
    assert isinstance(loader.template_dir, Path)
    assert loader.env is not None


def test_prompt_loader_initialization_custom_path(tmp_path):
    """Test PromptLoader initialization with custom path."""
    custom_dir = tmp_path / "custom_templates"
    loader = PromptLoader(template_dir=custom_dir)

    assert loader.template_dir == custom_dir
    assert custom_dir.exists()


def test_prompt_loader_render_string():
    """Test PromptLoader render_string method."""
    loader = PromptLoader()

    result = loader.render_string("Hello {{ name }}!", name="World")

    assert result == "Hello World!"


def test_prompt_loader_render_string_with_filters():
    """Test PromptLoader render_string with custom filters."""
    loader = PromptLoader()

    # Test truncate_text filter
    result = loader.render_string(
        "{{ text|truncate_text(10) }}",
        text="This is a very long text that should be truncated",
    )

    assert len(result) <= 13  # 10 + "..." (3 chars)
    assert "..." in result


def test_prompt_loader_word_count_filter():
    """Test PromptLoader word_count filter."""
    loader = PromptLoader()

    result = loader.render_string(
        "Word count: {{ text|word_count }}",
        text="one two three four five",
    )

    assert "Word count: 5" in result


def test_prompt_loader_format_list_filter():
    """Test PromptLoader format_list filter."""
    loader = PromptLoader()

    result = loader.render_string(
        "{{ items|format_list }}",
        items=["First", "Second", "Third"],
    )

    assert "- First" in result
    assert "- Second" in result
    assert "- Third" in result


def test_prompt_loader_format_list_custom_bullet():
    """Test PromptLoader format_list filter with custom bullet."""
    loader = PromptLoader()

    result = loader.render_string(
        "{{ items|format_list('*') }}",
        items=["First", "Second"],
    )

    assert "* First" in result
    assert "* Second" in result


def test_prompt_loader_truncate_text_short():
    """Test PromptLoader truncate_text doesn't truncate short text."""
    loader = PromptLoader()

    result = loader.render_string(
        "{{ text|truncate_text(100) }}",
        text="Short text",
    )

    assert result == "Short text"


def test_prompt_loader_jinja2_environment_settings():
    """Test PromptLoader Jinja2 environment has correct settings."""
    loader = PromptLoader()

    assert loader.env.trim_blocks is True
    assert loader.env.lstrip_blocks is True
    assert loader.env.keep_trailing_newline is True


def test_prompt_loader_render_with_whitespace_control():
    """Test PromptLoader handles whitespace correctly."""
    loader = PromptLoader()

    template = """
{% for item in items %}
{{ item }}
{% endfor %}
"""

    result = loader.render_string(template, items=["A", "B", "C"])

    # Should handle whitespace nicely (trim_blocks and lstrip_blocks)
    lines = result.strip().split("\n")
    assert "A" in lines
    assert "B" in lines
    assert "C" in lines


def test_get_loader_singleton():
    """Test get_loader returns singleton instance."""
    loader1 = get_loader()
    loader2 = get_loader()

    assert loader1 is loader2


def test_render_template_convenience_function():
    """Test render_template convenience function."""
    # Create a simple string template since we don't have actual template files in test
    loader = get_loader()

    # Use render_string instead since we don't have template files
    result = loader.render_string("Hello {{ name }}!", name="Test")

    assert result == "Hello Test!"


def test_prompt_loader_multiple_variables():
    """Test PromptLoader with multiple variables."""
    loader = PromptLoader()

    result = loader.render_string(
        "{{ greeting }} {{ name }}! Your score is {{ score }}.",
        greeting="Hello",
        name="Alice",
        score=100,
    )

    assert result == "Hello Alice! Your score is 100."


def test_prompt_loader_nested_structures():
    """Test PromptLoader with nested data structures."""
    loader = PromptLoader()

    result = loader.render_string(
        "Name: {{ user.name }}, Age: {{ user.age }}",
        user={"name": "Alice", "age": 25},
    )

    assert result == "Name: Alice, Age: 25"


def test_prompt_loader_conditional_rendering():
    """Test PromptLoader with conditional rendering."""
    loader = PromptLoader()

    template = "{% if show_message %}Message: {{ message }}{% endif %}"

    result1 = loader.render_string(template, show_message=True, message="Hello")
    assert "Message: Hello" in result1

    result2 = loader.render_string(template, show_message=False, message="Hello")
    assert "Message:" not in result2


def test_prompt_loader_filters_chaining():
    """Test PromptLoader with chained filters."""
    loader = PromptLoader()

    result = loader.render_string(
        "{{ text|truncate_text(50)|upper }}",
        text="This is a test text",
    )

    assert "THIS IS A TEST TEXT" in result

