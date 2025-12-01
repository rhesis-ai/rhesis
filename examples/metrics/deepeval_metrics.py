"""
Comprehensive examples of all DeepEval metrics in the Rhesis SDK.

This script demonstrates how to use each DeepEval metric with realistic test cases
that show both passing and failing scenarios for each metric type.

Available DeepEval Metrics:
1. DeepEvalAnswerRelevancy - Measures how relevant the answer is to the question
2. DeepEvalFaithfulness - Measures how faithful the answer is to the provided context
3. DeepEvalContextualRelevancy - Measures how relevant the context is to the question
4. DeepEvalContextualPrecision - Measures precision of retrieved context
5. DeepEvalContextualRecall - Measures recall of relevant context
"""

import asyncio

from rhesis.sdk.metrics.providers.deepeval import (
    DeepEvalAnswerRelevancy,
    DeepEvalContextualPrecision,
    DeepEvalContextualRecall,
    DeepEvalContextualRelevancy,
    DeepEvalFaithfulness,
)
from rhesis.sdk.models.factory import get_model

model = get_model("rhesis")


def print_metric_result(metric_name: str, test_name: str, result, threshold: float):
    """Helper function to print metric results in a readable format."""
    print(f"\n{'=' * 60}")
    print(f"METRIC: {metric_name}")
    print(f"TEST: {test_name}")
    print(f"{'=' * 60}")
    print(f"Score: {result.score:.3f}")
    print(f"Threshold: {threshold}")
    print(f"Passed: {'✅ YES' if result.score >= threshold else '❌ NO'}")
    print(f"Details: {result.details}")
    print(f"{'=' * 60}")


async def test_answer_relevancy():
    """Test DeepEvalAnswerRelevancy metric with passing and failing cases."""
    print("\n🔍 TESTING ANSWER RELEVANCY METRIC")

    # Initialize the metric
    metric = DeepEvalAnswerRelevancy(threshold=0.7, model=model)

    # Test Case 1: PASSING - Highly relevant answer
    input = "What is the capital of France?"
    output = (
        "The capital of France is Paris, which is located in the north-central part of the country."
    )
    expected_output = "Paris"
    context = [
        "France is a country in Western Europe.",
        "Paris is the capital and largest city of France.",
    ]

    result = metric.evaluate(input, output, expected_output, context)
    print_metric_result(
        "Answer Relevancy",
        "PASSING - Direct answer to question",
        result,
        metric.threshold,
    )

    # Test Case 2: FAILING - Irrelevant answer
    input = "What is the capital of France?"
    output = (
        "I love pizza and Italian food. The weather is nice today. "
        "Did you know that cats are amazing pets?"
    )
    expected_output = "Paris"
    context = [
        "France is a country in Western Europe.",
        "Paris is the capital and largest city of France.",
    ]

    result = metric.evaluate(input, output, expected_output, context)
    print_metric_result(
        "Answer Relevancy",
        "FAILING - Completely irrelevant answer",
        result,
        metric.threshold,
    )


async def test_faithfulness():
    """Test DeepEvalFaithfulness metric with passing and failing cases."""
    print("\n🔍 TESTING FAITHFULNESS METRIC")

    # Initialize the metric
    metric = DeepEvalFaithfulness(threshold=0.8, model=model)

    # Test Case 1: PASSING - Answer faithful to context
    input = "What is the population of Tokyo?"
    output = (
        "According to the provided information, "
        "Tokyo has a population of approximately 14 million people."
    )
    expected_output = None  # Faithfulness doesn't require ground truth
    context = [
        "Tokyo is the capital of Japan.",
        "Tokyo has a population of approximately 14 million people.",
        "Tokyo is one of the most populous metropolitan areas in the world.",
    ]

    result = metric.evaluate(input, output, expected_output, context)
    print_metric_result(
        "Faithfulness",
        "PASSING - Answer based on provided context",
        result,
        metric.threshold,
    )

    # Test Case 2: FAILING - Answer contradicts context
    input = "What is the population of Tokyo?"
    output = "Tokyo has a population of 50 million people, making it the largest city in the world."
    expected_output = None
    context = [
        "Tokyo is the capital of Japan.",
        "Tokyo has a population of approximately 14 million people.",
        "Tokyo is one of the most populous metropolitan areas in the world.",
    ]

    result = metric.evaluate(input, output, expected_output, context)
    print_metric_result(
        "Faithfulness",
        "FAILING - Answer contradicts provided context",
        result,
        metric.threshold,
    )


async def test_contextual_relevancy():
    """Test DeepEvalContextualRelevancy metric with passing and failing cases."""
    print("\n🔍 TESTING CONTEXTUAL RELEVANCY METRIC")

    # Initialize the metric
    metric = DeepEvalContextualRelevancy(threshold=0.6, model=model)

    # Test Case 1: PASSING - Highly relevant context
    input = "How do I bake a chocolate cake?"
    output = (
        "To bake a chocolate cake, you'll need flour, sugar, cocoa powder, eggs, and butter. "
        "Mix the dry ingredients, then add wet ingredients, and bake at 350°F for 30 minutes."
    )
    expected_output = None
    context = [
        "Chocolate cake recipes typically require flour, sugar, cocoa powder, eggs, and butter.",
        "The standard baking temperature for cakes is 350°F and baking time is 25-35 minutes.",
        "Mix dry ingredients first, then gradually add wet ingredients for best results.",
    ]

    result = metric.evaluate(input, output, expected_output, context)
    print_metric_result(
        "Contextual Relevancy",
        "PASSING - Context directly relevant to question",
        result,
        metric.threshold,
    )

    # Test Case 2: FAILING - Irrelevant context
    input = "How do I bake a chocolate cake?"
    output = "To bake a chocolate cake, you'll need flour, sugar, cocoa powder, eggs, and butter."
    expected_output = None
    context = [
        "The weather forecast shows rain for the next three days.",
        "Stock market prices have been fluctuating recently.",
        "The latest smartphone models were released last month.",
    ]

    result = metric.evaluate(input, output, expected_output, context)
    print_metric_result(
        "Contextual Relevancy",
        "FAILING - Context completely irrelevant to question",
        result,
        metric.threshold,
    )


async def test_contextual_precision():
    """Test DeepEvalContextualPrecision metric with passing and failing cases."""
    print("\n🔍 TESTING CONTEXTUAL PRECISION METRIC")

    # Initialize the metric
    metric = DeepEvalContextualPrecision(threshold=0.7, model=model)

    # Test Case 1: PASSING - High precision context (all relevant)
    input = "What are the benefits of regular exercise?"
    output = (
        "Regular exercise provides numerous health benefits including improved "
        "cardiovascular health, stronger muscles, better mental health, and increased longevity."
    )
    expected_output = (
        "Regular exercise provides numerous health benefits including improved "
        "cardiovascular health, stronger muscles, better mental health, and increased longevity."
    )
    context = [
        "Exercise improves cardiovascular health by strengthening the heart muscle.",
        "Regular physical activity builds and maintains muscle strength and endurance.",
        "Exercise releases endorphins which improve mood and mental health.",
        "Studies show that regular exercise can increase life expectancy by 3-7 years.",
    ]

    result = metric.evaluate(input, output, expected_output, context)
    print_metric_result(
        "Contextual Precision",
        "PASSING - All context chunks are highly relevant",
        result,
        metric.threshold,
    )

    # Test Case 2: FAILING - Low precision context (mixed relevance)
    input = "What are the benefits of regular exercise?"
    output = (
        "Regular exercise provides numerous health benefits including improved "
        "cardiovascular health and stronger muscles."
    )
    expected_output = (
        "Regular exercise provides numerous health benefits including "
        "improved cardiovascular health and stronger muscles."
    )
    context = [
        "Exercise improves cardiovascular health by strengthening the heart muscle.",
        "The capital of France is Paris.",
        "Regular physical activity builds and maintains muscle strength.",
        "Pizza is a popular Italian dish with various toppings.",
        "Studies show that regular exercise can increase life expectancy.",
    ]

    result = metric.evaluate(input, output, expected_output, context)
    print_metric_result(
        "Contextual Precision",
        "FAILING - Context contains irrelevant information",
        result,
        metric.threshold,
    )


async def test_contextual_recall():
    """Test DeepEvalContextualRecall metric with passing and failing cases."""
    print("\n🔍 TESTING CONTEXTUAL RECALL METRIC")

    # Initialize the metric
    metric = DeepEvalContextualRecall(threshold=0.8, model=model)

    # Test Case 1: PASSING - High recall (comprehensive context coverage)
    input = "Tell me about renewable energy sources."
    output = (
        "Renewable energy sources include solar power, wind energy, hydroelectric power, "
        "and geothermal energy. Solar power harnesses sunlight through photovoltaic cells, "
        "wind energy uses turbines to convert wind into electricity, hydroelectric power "
        "generates electricity from flowing water, and geothermal energy taps into the "
        "Earth's heat."
    )
    expected_output = (
        "Renewable energy sources include solar power, wind energy, hydroelectric power, "
        "and geothermal energy. Solar power harnesses sunlight through photovoltaic cells, "
        "wind energy uses turbines to convert wind into electricity, hydroelectric power "
        "generates electricity from flowing water, and geothermal energy taps into the "
        "Earth's heat."
    )
    context = [
        "Solar power harnesses sunlight through photovoltaic cells to generate electricity.",
        "Wind energy uses turbines to convert wind into electrical power.",
        "Hydroelectric power generates electricity from flowing water in dams.",
        "Geothermal energy taps into the Earth's internal heat for power generation.",
        "These renewable sources help reduce greenhouse gas emissions.",
    ]

    result = metric.evaluate(input, output, expected_output, context)
    print_metric_result(
        "Contextual Recall",
        "PASSING - Answer covers most relevant context information",
        result,
        metric.threshold,
    )

    # Test Case 2: FAILING - Low recall (incomplete context coverage)
    input = "Tell me about renewable energy sources."
    output = "Renewable energy sources include solar power and wind energy."
    expected_output = "Renewable energy sources include solar power and wind energy."
    context = [
        "Solar power harnesses sunlight through photovoltaic cells to generate electricity.",
        "Wind energy uses turbines to convert wind into electrical power.",
        "Hydroelectric power generates electricity from flowing water in dams.",
        "Geothermal energy taps into the Earth's internal heat for power generation.",
        "Nuclear power uses uranium fission to generate electricity.",
        "These renewable sources help reduce greenhouse gas emissions.",
    ]

    result = metric.evaluate(input, output, expected_output, context)
    print_metric_result(
        "Contextual Recall",
        "FAILING - Answer misses important context information",
        result,
        metric.threshold,
    )


async def test_all_metrics():
    """Run all metric tests with different model configurations."""
    print("🚀 STARTING COMPREHENSIVE DEEP EVAL METRICS TESTING")
    print("=" * 80)

    # Test with default model
    print("\n📋 Testing with default Rhesis model...")
    await test_answer_relevancy()
    await test_faithfulness()
    await test_contextual_relevancy()
    await test_contextual_precision()
    await test_contextual_recall()

    print("\n🎯 ALL TESTS COMPLETED!")
    print("\nSummary of DeepEval Metrics:")
    print("1. Answer Relevancy - Measures how relevant the answer is to the question")
    print("2. Faithfulness - Measures how faithful the answer is to the provided context")
    print("3. Contextual Relevancy - Measures how relevant the context is to the question")
    print("4. Contextual Precision - Measures precision of retrieved context")
    print("5. Contextual Recall - Measures recall of relevant context")


def demonstrate_metric_factory():
    """Demonstrate how to use the DeepEval metric factory."""
    print("\n🏭 DEEP EVAL METRIC FACTORY DEMONSTRATION")
    print("=" * 50)

    from rhesis.sdk.metrics.providers.deepeval import DeepEvalMetricFactory

    # Create factory instance
    factory = DeepEvalMetricFactory()

    # List available metrics
    print("Available DeepEval metrics:")
    for metric_name in factory.list_supported_metrics():
        print(f"  - {metric_name}")

    # Create metrics using factory
    print("\nCreating metrics using factory...")

    # Create Answer Relevancy metric
    answer_relevancy = factory.create("DeepEvalAnswerRelevancy", threshold=0.8, model=model)
    print(f"Created: {answer_relevancy.name} (threshold: {answer_relevancy.threshold})")

    # Create Faithfulness metric
    faithfulness = factory.create("DeepEvalFaithfulness", threshold=0.7, model=model)
    print(f"Created: {faithfulness.name} (threshold: {faithfulness.threshold})")

    # Create Contextual Precision metric
    contextual_precision = factory.create("DeepEvalContextualPrecision", threshold=0.6, model=model)
    print(f"Created: {contextual_precision.name} (threshold: {contextual_precision.threshold})")


async def main():
    """Main function to run all examples."""
    print("🎯 Rhesis SDK DeepEval Metrics Examples")
    print("=" * 80)

    # Demonstrate metric factory usage
    demonstrate_metric_factory()

    # Run comprehensive metric tests
    await test_all_metrics()

    print("\n✨ Example completed successfully!")
    print("\nTo run individual metric tests, you can call:")
    print("  - await test_answer_relevancy()")
    print("  - await test_faithfulness()")
    print("  - await test_contextual_relevancy()")
    print("  - await test_contextual_precision()")
    print("  - await test_contextual_recall()")


if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())
