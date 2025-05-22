# Rhesis Custom Metrics

This package contains Rhesis' own custom metrics implementations that can be used to evaluate LLM responses.

## Metrics

### RhesisPromptMetric

A generic metric that evaluates outputs based on a custom prompt template. It uses an LLM to perform evaluation based on provided evaluation criteria.

#### Features:
- Supports customizable evaluation prompts, steps, and reasoning
- Uses Mirascope's structured response models for robust parsing
- Provides both raw and normalized scores
- Includes detailed evaluation reasoning

#### Usage:
```python
from rhesis.backend.metrics.rhesis import RhesisPromptMetric

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

### RhesisDetailedPromptMetric

An extension of RhesisPromptMetric that provides multiple scores for different aspects of the evaluation using a more detailed response model.

#### Features:
- Evaluates responses across multiple dimensions
- Returns separate scores for relevance, accuracy, and coherence
- Includes an overall score and detailed reasoning
- Uses the same interface as RhesisPromptMetric

#### Usage:
```python
from rhesis.backend.metrics.rhesis import RhesisDetailedPromptMetric

detailed_metric = RhesisDetailedPromptMetric(
    name="Multi-Dimensional Evaluation",
    evaluation_prompt="...",
    evaluation_steps="...",
    reasoning="...",
    min_score=1.0,
    max_score=5.0,
    threshold=0.6
)

result = detailed_metric.evaluate(
    input="User query",
    output="LLM response to evaluate",
    expected_output="Ground truth",
    context=[]
)

print(f"Overall score: {result.details['raw_score']}")
print(f"Relevance: {result.details['relevance_score']}")
print(f"Accuracy: {result.details['accuracy_score']}")
print(f"Coherence: {result.details['coherence_score']}")
print(f"Reasoning: {result.details['reasoning']}")
```

## Factory

The `RhesisMetricFactory` provides a way to create Rhesis metric instances by name:

```python
from rhesis.backend.metrics.rhesis import RhesisMetricFactory

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