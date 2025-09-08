# Rhesis Custom Metrics

This package contains Rhesis' own custom metrics implementations that can be used to evaluate LLM responses.

## Metrics

### RhesisPromptMetric

A generic metric that evaluates outputs based on a custom prompt template. It uses an LLM to perform evaluation based on provided evaluation criteria.

#### Features:
- Supports customizable evaluation prompts, steps, and reasoning
- Uses structured response models (Pydantinc and JSON Schema) for robust parsing
- Provides both raw and normalized scores
- Includes detailed evaluation reasoning

#### Usage:

```python
from rhesis.sdk.metrics.providers.native import RhesisPromptMetric

metric = RhesisPromptMetric(
    name="My Custom Metric",
    evaluation_prompt="The detailed criteria for evaluation...",
    evaluation_steps="Step-by-step process for evaluation...",
    reasoning="How to apply reasoning to the evaluation...",
    min_score=1.0,
    max_score=5.0,
    threshold=0.6,
    provider="openai",
    model="gpt-4o"
)

result = metric.evaluate(
    input="User query",
    output="LLM response to evaluate",
    expected_output="Ground truth or reference response",
    context=["Optional context chunks"]
)

print(f"Score: {result.score}")
print(f"Reason: {result.details['reason']}")
print(f"Successful: {result.details['is_successful']}")
```

## Factory

The `RhesisMetricFactory` provides a way to create Rhesis metric instances by name:

```python
from rhesis.sdk.metrics.providers.native import RhesisMetricFactory

factory = RhesisMetricFactory()
metric = factory.create(
    "RhesisPromptMetric",
    name="Coherence Evaluation",
    evaluation_prompt="...",
    evaluation_steps="...",
    reasoning="...",
    min_score=1.0,
    max_score=5.0,
    threshold=0.6
)

# List all available metrics
available_metrics = factory.list_supported_metrics()
print(f"Available metrics: {available_metrics}")
```

## Testing

To run the tests for the Rhesis metrics, use pytest from the backend directory:

```bash
# Run all Rhesis metric tests
python -m pytest src/rhesis/backend/metrics/tests/test_rhesis.py -v

# Run a specific test
python -m pytest src/rhesis/backend/metrics/tests/test_rhesis.py::test_rhesis_prompt_metric_init -v

# Run tests with coverage
python -m pytest src/rhesis/backend/metrics/tests/test_rhesis.py --cov=rhesis.sdk.metrics.providers.native
```

The test suite includes:
- Metric initialization validation
- Evaluation functionality with mocked LLM responses
- Prompt template generation
- Threshold validation
- Error handling scenarios
