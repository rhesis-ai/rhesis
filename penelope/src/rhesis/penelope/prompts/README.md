# Penelope Prompts Module

Centralized, versioned, and testable prompt management for Penelope.

## Overview

All prompts used by Penelope are defined in this module for:
- **Centralization**: Single source of truth for all prompts
- **Versioning**: Track changes and enable A/B testing
- **Testing**: Unit test prompts independently
- **Maintainability**: Clear ownership and documentation

## Structure

```
prompts/
├── __init__.py                         # Main exports
├── base.py                             # PromptTemplate base class (supports Jinja2)
├── loader.py                           # Jinja2 template loader
├── templates/                          # Jinja2 template files (.j2)
│   ├── goal_evaluation.j2              # Goal evaluation template
│   └── system_prompt.j2                # System prompt template
├── system/                             # System-level prompts
│   ├── core_instructions.py            # Penelope's identity and behavior
│   ├── system_assembly.py              # Python-based system prompt assembly
│   └── system_assembly_jinja.py        # Jinja2-based system prompt assembly
├── agent/                              # Agent execution prompts
│   ├── turn_prompts.py                 # Turn-by-turn guidance
│   └── default_instructions.py         # Default test instructions
└── evaluation/                         # Evaluation prompts
    └── goal_evaluation.py              # Goal achievement evaluation (Jinja2)
```

## Usage

### Basic Import

```python
from rhesis.penelope.prompts import (
    BASE_INSTRUCTIONS_PROMPT,
    FIRST_TURN_PROMPT,
    SUBSEQUENT_TURN_PROMPT,
    DEFAULT_INSTRUCTIONS_TEMPLATE,
    GOAL_EVALUATION_PROMPT,
    get_system_prompt,
)
```

### Using Prompt Templates

#### Python Format (Simple)

```python
# Simple rendering (no variables)
first_turn = FIRST_TURN_PROMPT.render()

# Rendering with variables
instructions = DEFAULT_INSTRUCTIONS_TEMPLATE.render(
    goal="Test multi-turn conversation"
)

# Complex assembly
system_prompt = get_system_prompt(
    test_instructions="Test the chatbot",
    goal="Verify behavior",
    context="Additional context",
    available_tools="tool1, tool2"
)
```

#### Jinja2 Format (Advanced)

```python
from rhesis.penelope.prompts import (
    TemplateFormat,
    PromptTemplate,
    get_system_prompt_jinja,
    render_template,
)

# Inline Jinja2 template
template = PromptTemplate(
    version="1.0.0",
    name="my_prompt",
    description="Custom prompt with conditionals",
    format=TemplateFormat.JINJA2,
    template="""
    Test: {{ test_name }}
    {% if context %}
    Context: {{ context }}
    {% endif %}
    """
)
rendered = template.render(test_name="Auth Test", context="User data")

# File-based Jinja2 template
template = PromptTemplate(
    version="1.0.0",
    name="my_prompt",
    description="Custom prompt from file",
    format=TemplateFormat.JINJA2_FILE,
    template="my_template.j2"  # File in templates/ directory
)
rendered = template.render(var1="value1", var2="value2")

# Direct template rendering
from rhesis.penelope.prompts import render_template
result = render_template("goal_evaluation.j2", goal="Test goal", conversation="...")
```

### Accessing Metadata

```python
# Check version
print(GOAL_EVALUATION_PROMPT.version)  # "2.0.0"

# Check name
print(FIRST_TURN_PROMPT.name)  # "first_turn"

# View changelog
print(GOAL_EVALUATION_PROMPT.metadata["changelog"])
```

## Prompt Catalog

### System Prompts

| Prompt | Version | Format | Purpose |
|--------|---------|--------|---------|
| `BASE_INSTRUCTIONS_PROMPT` | 1.0.0 | Python | Defines Penelope's core identity and behavior |
| `get_system_prompt()` | - | Python | Assembles complete system prompt for test |
| `SYSTEM_PROMPT_TEMPLATE` | 2.0.0 | Jinja2 File | Jinja2-based system prompt with conditionals |
| `get_system_prompt_jinja()` | - | Jinja2 File | Assembles system prompt using Jinja2 |

### Agent Prompts

| Prompt | Version | Format | Purpose |
|--------|---------|--------|---------|
| `FIRST_TURN_PROMPT` | 1.0.0 | Python | Guides initial turn execution |
| `SUBSEQUENT_TURN_PROMPT` | 1.0.0 | Python | Guides subsequent turns |
| `DEFAULT_INSTRUCTIONS_TEMPLATE` | 1.0.0 | Python | Generates default instructions from goal |

### Evaluation Prompts

| Prompt | Version | Format | Purpose |
|--------|---------|--------|---------|
| `GOAL_EVALUATION_PROMPT` | 3.0.0 | Jinja2 File | Evaluates goal achievement (criterion-by-criterion) |

## Adding New Prompts

1. **Create prompt file** in appropriate subdirectory
2. **Define PromptTemplate**:
   ```python
   from rhesis.penelope.prompts.base import PromptTemplate
   
   MY_NEW_PROMPT = PromptTemplate(
       version="1.0.0",
       name="my_prompt",
       description="What this prompt does",
       metadata={
           "author": "Your Name",
           "changelog": {
               "1.0.0": "Initial version"
           }
       },
       template="""Your prompt text here
       
       Can use {placeholders} for variables."""
   )
   ```
3. **Export** in `__init__.py`
4. **Document** in this README

## Versioning Guidelines

Follow semantic versioning (MAJOR.MINOR.PATCH):
- **MAJOR**: Breaking changes to prompt structure or behavior
- **MINOR**: New features or significant enhancements
- **PATCH**: Bug fixes, typos, minor clarifications

Example changelog:
```python
metadata = {
    "changelog": {
        "1.0.0": "Initial version",
        "1.1.0": "Added criterion-by-criterion evaluation",
        "2.0.0": "Changed response format (breaking change)"
    }
}
```

## Testing Prompts

Test prompts independently:

```python
def test_first_turn_prompt():
    """Test first turn prompt renders correctly."""
    prompt = FIRST_TURN_PROMPT.render()
    assert "Begin executing" in prompt
    assert len(prompt) > 0

def test_default_instructions():
    """Test default instructions include goal."""
    goal = "Test authentication"
    instructions = DEFAULT_INSTRUCTIONS_TEMPLATE.render(goal=goal)
    assert goal in instructions
    assert "Systematically test" in instructions
```

## Migration from Old System

The old `instructions.py` module has been deprecated. It now re-exports from this module for backward compatibility:

```python
# Old (deprecated)
from rhesis.penelope.instructions import BASE_INSTRUCTIONS, get_system_prompt

# New (recommended)
from rhesis.penelope.prompts import BASE_INSTRUCTIONS_PROMPT, get_system_prompt
system_prompt = BASE_INSTRUCTIONS_PROMPT.template
```

## Jinja2 Templating Features

### Why Jinja2?

Jinja2 provides powerful features beyond simple Python string formatting:
- **Conditionals**: Show/hide sections based on variables
- **Loops**: Iterate over lists and dicts
- **Filters**: Transform variables (truncate, format, etc.)
- **Template Inheritance**: Reuse common structures
- **Better Readability**: Separate logic from content

### Template Formats

Penelope supports three template formats:

1. **Python** (`TemplateFormat.PYTHON`):
   - Simple `{placeholder}` syntax
   - Fast and lightweight
   - Good for simple prompts
   ```python
   template="Hello {name}!"
   ```

2. **Jinja2 Inline** (`TemplateFormat.JINJA2`):
   - Full Jinja2 features in a string
   - Conditionals, loops, filters
   - Good for medium complexity
   ```python
   template="Hello {{ name }}! {% if context %}Context: {{ context }}{% endif %}"
   ```

3. **Jinja2 File** (`TemplateFormat.JINJA2_FILE`):
   - External `.j2` template files
   - Best for complex prompts
   - Easier to edit and version
   ```python
   template="my_template.j2"  # File in templates/ directory
   ```

### Jinja2 Examples

#### Conditionals

```jinja2
{% if context %}
**Context & Resources:**
{{ context }}
{% endif %}

{% if tools %}
**Available Tools:**
{{ tools }}
{% else %}
No tools available for this test.
{% endif %}
```

#### Loops

```jinja2
**Your Tools:**
{% for tool in tools %}
- {{ tool.name }}: {{ tool.description }}
{% endfor %}

**Test Criteria:**
{% for criterion in criteria %}
{{ loop.index }}. {{ criterion }}
{% endfor %}
```

#### Filters

```jinja2
{# Truncate long text #}
Summary: {{ long_text | truncate_text(100) }}

{# Count words #}
This has {{ text | word_count }} words

{# Format lists #}
{{ items | format_list("-") }}

{# Upper/lower case #}
{{ name | upper }}
{{ name | lower }}

{# Default values #}
{{ optional_var | default("Not provided") }}
```

### Custom Filters

Penelope includes custom Jinja2 filters:

```python
from rhesis.penelope.prompts import get_loader

loader = get_loader()

# truncate_text: Shorten long strings
result = loader.render_string(
    "{{ text | truncate_text(50) }}",
    text="Very long text..."
)

# word_count: Count words
result = loader.render_string(
    "Words: {{ text | word_count }}",
    text="Hello world from Penelope"
)

# format_list: Format lists with bullets
result = loader.render_string(
    "{{ items | format_list('•') }}",
    items=["First", "Second", "Third"]
)
```

### Creating Template Files

1. Create `.j2` file in `prompts/templates/`:
```jinja2
{# templates/my_prompt.j2 #}
Test Goal: {{ goal }}

{% if instructions %}
Instructions:
{{ instructions }}
{% endif %}

{% for i in range(1, steps + 1) %}
Step {{ i }}: {{ step_descriptions[i-1] }}
{% endfor %}
```

2. Define PromptTemplate:
```python
MY_PROMPT = PromptTemplate(
    version="1.0.0",
    name="my_prompt",
    description="Custom prompt with loops",
    format=TemplateFormat.JINJA2_FILE,
    template="my_prompt.j2"
)
```

3. Use it:
```python
result = MY_PROMPT.render(
    goal="Test authentication",
    instructions="Be thorough",
    steps=3,
    step_descriptions=["Login", "Verify", "Logout"]
)
```

### Advanced Features

#### Template Inheritance (Future)

```jinja2
{# base_test.j2 #}
Test: {{ test_name }}
{% block instructions %}{% endblock %}
{% block execution %}{% endblock %}

{# auth_test.j2 #}
{% extends "base_test.j2" %}
{% block instructions %}
Test authentication flows
{% endblock %}
```

#### Macros (Reusable Blocks)

```jinja2
{% macro test_section(title, content) %}
**{{ title }}:**
{{ content }}
---
{% endmacro %}

{{ test_section("Goal", goal) }}
{{ test_section("Context", context) }}
```

## Future Enhancements

- [x] Jinja2 template support for complex prompts ✅
- [ ] Template inheritance for reusable structures
- [ ] Macro library for common patterns
- [ ] Prompt registry for A/B testing
- [ ] Localization support (multi-language)
- [ ] Prompt observability (track which versions are used)
- [ ] Automated prompt optimization tools
- [ ] Template validation and testing utilities

## References

- [Anthropic's Prompt Engineering Guide](https://docs.anthropic.com/claude/docs/prompt-engineering)
- [OpenAI's Best Practices](https://platform.openai.com/docs/guides/prompt-engineering)
- Penelope Design Document: `docs/MULTI_TURN_METRICS_DESIGN.md`

