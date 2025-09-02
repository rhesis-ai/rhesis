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
    """Example using the default Rhesis model.
    When the model provider is not specified, Rhesis model will be used.

    """

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


def example_with_gemini_model():
    """Example using Gemini model (requires GEMINI_API_KEY env var).
    The model can be specified as a string or instance of BaseLLM.
    """

    metric = DeepEvalAnswerRelevancy(threshold=0.8, model="gemini/gemini-2.0-flash")

    result = metric.evaluate(
        input="What is machine learning?",
        output="Machine learning is a subset of artificial intelligence that enables computers to "
        "learn from data.",
        expected_output="Machine learning is a method of data analysis that automates analytical "
        "model building.",
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
    example_with_default_model()
    print("=" * 50)
    example_with_gemini_model()
    print("=" * 50)
