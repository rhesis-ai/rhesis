#!/usr/bin/env python
"""
Runner script for metric evaluation examples.
Use this script to run evaluator examples without import issues.
"""

from typing import Any, Dict

from rhesis.backend.metrics.base import MetricConfig
from rhesis.backend.metrics.evaluator import MetricEvaluator


def main():
    """Run example metric evaluations."""
    # Example usage
    sample_input = {
        "input_text": "What is the capital of France?",
        "output_text": "The capital of France is Paris. It is known as the City of Light.",
        "expected_output": "Paris is the capital of France.",
        "context": [
            "Paris is the capital and largest city of France.",
            "Known as the City of Light, Paris is a global center for art, culture, and fashion.",
        ],
    }

    # Create evaluator
    evaluator = MetricEvaluator()

    # Example: Evaluate specific metrics with explicit configurations
    results = evaluator.evaluate(
        metrics=[
            # Using MetricConfig objects
            MetricConfig(
                class_name="DeepEvalAnswerRelevancy",
                backend="deepeval",
                threshold=0.7,
                description="Measures how relevant the answer is to the question"
            ),
            # Using dictionaries (will be converted to MetricConfig)
            {
                "class_name": "DeepEvalFaithfulness", 
                "backend": "deepeval",
                "threshold": 0.8,
                "description": "Measures how faithful the answer is to the context",
            },
        ],
        **sample_input,
    )

    # Print results in a readable format
    print_results(results, "Evaluation Results")


def print_results(results: Dict[str, Any], title: str):
    """Print metric evaluation results in a readable format."""
    print(f"\n{title}")
    print("=" * len(title))
    for class_name, metric_results in results.items():
        print(f"\n{class_name}:")
        print(f"Description: {metric_results['description']}")
        print(f"Backend: {metric_results['backend']}")
        print(f"Score: {metric_results['score']:.2f}")
        print(f"Success: {metric_results['is_successful']}")
        print(f"Reason: {metric_results['reason']}")
        print(f"Threshold: {metric_results['threshold']}")
        print("-" * 50)


if __name__ == "__main__":
    main() 