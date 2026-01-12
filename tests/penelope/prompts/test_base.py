"""Tests for prompt base classes."""

import pytest
from pydantic import ValidationError

from rhesis.penelope.prompts.base import PromptTemplate, TemplateFormat


def test_template_format_enum_values():
    """Test TemplateFormat enum values."""
    assert TemplateFormat.PYTHON == "python"
    assert TemplateFormat.JINJA2 == "jinja2"
    assert TemplateFormat.JINJA2_FILE == "jinja2_file"


def test_prompt_template_creation():
    """Test PromptTemplate initialization."""
    template = PromptTemplate(
        version="1.0.0",
        name="test_prompt",
        description="Test prompt",
        template="Hello {name}!",
        format=TemplateFormat.PYTHON,
    )

    assert template.version == "1.0.0"
    assert template.name == "test_prompt"
    assert template.description == "Test prompt"
    assert template.template == "Hello {name}!"
    assert template.format == TemplateFormat.PYTHON


def test_prompt_template_defaults():
    """Test PromptTemplate default values."""
    template = PromptTemplate(
        name="test_prompt",
        description="Test prompt",
        template="Hello!",
    )

    assert template.version == "1.0.0"
    assert template.format == TemplateFormat.PYTHON
    assert template.metadata == {}


def test_prompt_template_with_metadata():
    """Test PromptTemplate with metadata."""
    metadata = {
        "author": "Test Author",
        "date": "2024-01-01",
        "changelog": "Initial version",
    }

    template = PromptTemplate(
        name="test_prompt",
        description="Test prompt",
        template="Test",
        metadata=metadata,
    )

    assert template.metadata == metadata
    assert template.metadata["author"] == "Test Author"


def test_prompt_template_render_python():
    """Test PromptTemplate render with Python format."""
    template = PromptTemplate(
        name="test_prompt",
        description="Test prompt",
        template="Hello {name}! Goal: {goal}",
        format=TemplateFormat.PYTHON,
    )

    result = template.render(name="Alice", goal="Test authentication")

    assert result == "Hello Alice! Goal: Test authentication"


def test_prompt_template_render_python_missing_variable():
    """Test PromptTemplate render raises error with missing variable."""
    template = PromptTemplate(
        name="test_prompt",
        description="Test prompt",
        template="Hello {name}!",
        format=TemplateFormat.PYTHON,
    )

    with pytest.raises(KeyError):
        template.render()  # Missing 'name'


def test_prompt_template_render_jinja2():
    """Test PromptTemplate render with Jinja2 format."""
    template = PromptTemplate(
        name="test_prompt",
        description="Test prompt",
        template="Hello {{ name }}! Goal: {{ goal }}",
        format=TemplateFormat.JINJA2,
    )

    result = template.render(name="Alice", goal="Test authentication")

    assert result == "Hello Alice! Goal: Test authentication"


def test_prompt_template_render_jinja2_with_defaults():
    """Test PromptTemplate render with Jinja2 and default values."""
    template = PromptTemplate(
        name="test_prompt",
        description="Test prompt",
        template="Hello {{ name|default('World') }}!",
        format=TemplateFormat.JINJA2,
    )

    # With value
    result1 = template.render(name="Alice")
    assert result1 == "Hello Alice!"

    # Without value (use default)
    result2 = template.render()
    assert result2 == "Hello World!"


def test_prompt_template_render_jinja2_with_conditions():
    """Test PromptTemplate render with Jinja2 conditional."""
    template = PromptTemplate(
        name="test_prompt",
        description="Test prompt",
        template="{% if premium %}Premium user{% else %}Regular user{% endif %}",
        format=TemplateFormat.JINJA2,
    )

    result1 = template.render(premium=True)
    assert "Premium user" in result1

    result2 = template.render(premium=False)
    assert "Regular user" in result2


def test_prompt_template_render_jinja2_with_loop():
    """Test PromptTemplate render with Jinja2 loop."""
    template = PromptTemplate(
        name="test_prompt",
        description="Test prompt",
        template="{% for item in items %}{{ item }}{% if not loop.last %}, {% endif %}{% endfor %}",
        format=TemplateFormat.JINJA2,
    )

    result = template.render(items=["one", "two", "three"])
    assert result == "one, two, three"


def test_prompt_template_render_unknown_format():
    """Test PromptTemplate render raises error for unknown format."""
    template = PromptTemplate(
        name="test_prompt",
        description="Test prompt",
        template="Test",
        format=TemplateFormat.PYTHON,
    )

    # Manually set an invalid format
    template.format = "invalid_format"  # type: ignore

    with pytest.raises(ValueError, match="Unknown template format"):
        template.render()


def test_prompt_template_str_representation():
    """Test PromptTemplate string representation."""
    template = PromptTemplate(
        name="test_prompt",
        version="2.0.0",
        description="Test prompt",
        template="Test",
        format=TemplateFormat.JINJA2,
    )

    str_repr = str(template)

    assert "test_prompt" in str_repr
    assert "2.0.0" in str_repr
    assert "jinja2" in str_repr


def test_prompt_template_validation():
    """Test PromptTemplate field validation."""
    # Should require name, description, template
    with pytest.raises(ValidationError):
        PromptTemplate(name="test")  # Missing description and template


def test_prompt_template_multiple_renders():
    """Test PromptTemplate can be rendered multiple times."""
    template = PromptTemplate(
        name="test_prompt",
        description="Test prompt",
        template="Hello {name}!",
        format=TemplateFormat.PYTHON,
    )

    result1 = template.render(name="Alice")
    result2 = template.render(name="Bob")

    assert result1 == "Hello Alice!"
    assert result2 == "Hello Bob!"


def test_prompt_template_complex_jinja2():
    """Test PromptTemplate with complex Jinja2 template."""
    template = PromptTemplate(
        name="test_prompt",
        description="Test prompt",
        template="""
Goal: {{ goal }}
Instructions:
{% for instruction in instructions %}
- {{ instruction }}
{% endfor %}
Status: {{ status|default('pending') }}
""",
        format=TemplateFormat.JINJA2,
    )

    result = template.render(
        goal="Test authentication",
        instructions=["Login", "Verify", "Logout"],
        status="active",
    )

    assert "Goal: Test authentication" in result
    assert "- Login" in result
    assert "- Verify" in result
    assert "- Logout" in result
    assert "Status: active" in result

