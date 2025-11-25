# Metric Prompts

This directory contains Jinja2 templates for LLM evaluation metric prompts.

## Purpose

Metric prompts are stored as templates to:
- Separate content from code for easier maintenance
- Enable non-developers to edit evaluation criteria
- Track prompt changes in version control
- Reuse prompts across different evaluators
- Leverage Jinja2 features (variables, conditionals, includes)

## Structure

Each metric typically has:
- `{metric_name}.jinja` - Main evaluation prompt
- `{metric_name}_steps.jinja` - Step-by-step evaluation instructions
- `{metric_name}_examples.jinja` - (Optional) Examples for the evaluator

## Available Metrics

### Refusal Detection
- `refusal_detection.jinja` - Detects when models refuse to follow instructions
- `refusal_detection_steps.jinja` - Evaluation steps

### Fluency
- `fluency.jinja` - Evaluates grammar, coherence, and naturalness
- `fluency_steps.jinja` - Evaluation steps

### Context Retention
- `context_retention.jinja` - Evaluates correct usage of provided context
- `context_retention_steps.jinja` - Evaluation steps
- `context_retention_examples.jinja` - Detailed examples

## Usage

Metrics load templates using Jinja2:

```python
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

PROMPTS_DIR = Path(__file__).parent.parent / "metric_prompts"
jinja_env = Environment(loader=FileSystemLoader(PROMPTS_DIR))

# Load template
evaluation_prompt = jinja_env.get_template("refusal_detection.jinja").render()
```

## Adding New Metrics

1. Create `{metric_name}.jinja` with the main prompt
2. Create `{metric_name}_steps.jinja` with evaluation steps
3. (Optional) Create `{metric_name}_examples.jinja` with examples
4. Update the metric class to load from templates
5. Update this README

## Editing Prompts

When editing prompts:
- Maintain consistent formatting and structure
- Test changes with actual evaluations
- Document significant changes in commit messages
- Consider backward compatibility with existing metrics
