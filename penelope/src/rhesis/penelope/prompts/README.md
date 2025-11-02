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
├── __init__.py                  # Main exports
├── base.py                      # PromptTemplate base class
├── system/                      # System-level prompts
│   ├── core_instructions.py     # Penelope's identity and behavior
│   └── system_assembly.py       # System prompt assembly
├── agent/                       # Agent execution prompts
│   ├── turn_prompts.py          # Turn-by-turn guidance
│   └── default_instructions.py  # Default test instructions
└── evaluation/                  # Evaluation prompts
    └── goal_evaluation.py       # Goal achievement evaluation
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

```python
# Simple rendering
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

| Prompt | Version | Purpose |
|--------|---------|---------|
| `BASE_INSTRUCTIONS_PROMPT` | 1.0.0 | Defines Penelope's core identity and behavior |
| `get_system_prompt()` | - | Assembles complete system prompt for test |

### Agent Prompts

| Prompt | Version | Purpose |
|--------|---------|---------|
| `FIRST_TURN_PROMPT` | 1.0.0 | Guides initial turn execution |
| `SUBSEQUENT_TURN_PROMPT` | 1.0.0 | Guides subsequent turns |
| `DEFAULT_INSTRUCTIONS_TEMPLATE` | 1.0.0 | Generates default instructions from goal |

### Evaluation Prompts

| Prompt | Version | Purpose |
|--------|---------|---------|
| `GOAL_EVALUATION_PROMPT` | 2.0.0 | Evaluates goal achievement (criterion-by-criterion) |

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

## Future Enhancements

- [ ] Jinja2 template support for complex prompts
- [ ] Prompt registry for A/B testing
- [ ] Localization support
- [ ] Prompt observability (track which versions are used)
- [ ] Automated prompt optimization tools

## References

- [Anthropic's Prompt Engineering Guide](https://docs.anthropic.com/claude/docs/prompt-engineering)
- [OpenAI's Best Practices](https://platform.openai.com/docs/guides/prompt-engineering)
- Penelope Design Document: `docs/MULTI_TURN_METRICS_DESIGN.md`

