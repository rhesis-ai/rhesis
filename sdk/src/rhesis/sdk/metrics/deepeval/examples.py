"""
Examples of using DeepEval metrics with different model configurations.

This file demonstrates how to use the updated DeepEval metrics with
 Rhesis LLM service.
"""

from rhesis.sdk.metrics.deepeval.metrics import (
    DeepEvalAnswerRelevancy,
    DeepEvalFaithfulness,
)


def example_with_default_model():
    """Example using the default Rhesis model (requires RHESIS_API_KEY env var).

    The model name will be read from RHESIS_MODEL_NAME environment variable,
    or default to 'rhesis-default' if not set.
    """

    # Use default model (Rhesis)
    # Model name comes from RHESIS_MODEL_NAME env var or defaults to 'rhesis-default'
    metric = DeepEvalAnswerRelevancy(threshold=0.8)

    # Example evaluation
    result = metric.evaluate(
        input="What is the capital of France?",
        output="The capital of France is Paris.",
        expected_output="Paris",
        context=["France is a country in Europe.", "Paris is the largest city in France."],
    )

    print(f"Score: {result.score}")
    print(f"Details: {result.details}")


# Future database configuration example
def example_future_database_config():
    """
    Example of how this could work with database configuration in the future.

    You would modify the get_model_from_config function in model_factory.py
    to read from your database instead of environment variables.
    """

    # This would come from your database
    database_model_config = {
        "type": "openai",
        "model_name": "gpt-4-turbo",
        "api_key": "encrypted_key_from_database",
        "extra_params": {"temperature": 0.2, "max_tokens": 1000},
    }

    metric = DeepEvalFaithfulness(threshold=0.8, model_config=database_model_config)  # noqa: F841

    print("This example shows how database config could work in the future")


def example_with_rhesis_model():
    """Example using Rhesis model (requires RHESIS_API_KEY env var).

    This example demonstrates how to use the RhesisModelWrapper that properly
    inherits from DeepEvalBaseLLM for seamless integration with DeepEval metrics.
    """

    model_config = {
        "type": "rhesis",
        "model_name": "rhesis-default",
        # API key will be read from RHESIS_API_KEY environment variable
        # or you can provide it directly
        # "api_key": "your-direct-api-key-here",
    }

    metric = DeepEvalAnswerRelevancy(threshold=0.8, model_config=model_config)

    result = metric.evaluate(
        input="What is machine learning?",
        output="Machine learning is a subset of artificial intelligence that enables computers to learn from data.",
        expected_output="Machine learning is a method of data analysis that automates analytical model building.",
        context=[
            "AI includes various technologies like machine learning.",
            "Machine learning algorithms improve with experience.",
        ],
    )

    print(f"Score: {result.score}")
    print(f"Details: {result.details}")


if __name__ == "__main__":
    print("DeepEval Metrics with Multiple Models - Examples")
    print("=" * 50)

    # Run examples (uncomment the ones you want to test)
    # Make sure you have the required environment variables set

    # example_with_default_model()
    # example_with_gemini_model()
    # example_with_openai_model()
    # example_with_anthropic_model()
    # example_with_azure_openai()
    # example_with_ollama()

    # example_with_custom_api_key()
    # example_future_database_config()
    example_with_rhesis_model()
