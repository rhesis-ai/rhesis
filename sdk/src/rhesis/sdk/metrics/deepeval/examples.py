"""
Examples of using DeepEval metrics with different model configurations.

This file demonstrates how to use the updated DeepEval metrics with various
models including Gemini, OpenAI, Anthropic, and others.
"""

from rhesis.backend.metrics.deepeval.metrics import (
    DeepEvalAnswerRelevancy,
    DeepEvalContextualRelevancy,
    DeepEvalFaithfulness,
)


def example_with_default_model():
    """Example using the default Gemini model (requires GEMINI_API_KEY env var).

    The model name will be read from GEMINI_MODEL_NAME environment variable,
    or default to 'gemini-1.5-pro' if not set.
    """

    # Use default model (Gemini)
    # Model name comes from GEMINI_MODEL_NAME env var or defaults to 'gemini-1.5-pro'
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


def example_with_gemini_model():
    """Example explicitly configuring Gemini model."""

    model_config = {
        "type": "gemini",
        "model_name": "gemini-1.5-pro",
        # API key will be read from GEMINI_API_KEY environment variable
    }

    metric = DeepEvalFaithfulness(threshold=0.7, model_config=model_config)

    result = metric.evaluate(
        input="Tell me about renewable energy.",
        output="Solar and wind power are renewable energy sources that help "
        "reduce carbon emissions.",
        expected_output=None,  # Faithfulness doesn't require ground truth
        context=[
            "Renewable energy comes from natural sources.",
            "Solar power uses sunlight to generate electricity.",
        ],
    )

    print(f"Score: {result.score}")
    print(f"Details: {result.details}")


def example_with_openai_model():
    """Example using OpenAI model (requires OPENAI_API_KEY env var)."""

    model_config = {
        "type": "openai",
        "model_name": "gpt-4",
        # API key will be read from OPENAI_API_KEY environment variable
    }

    metric = DeepEvalContextualRelevancy(threshold=0.6, model_config=model_config)

    result = metric.evaluate(
        input="How does photosynthesis work?",
        output="Photosynthesis is the process by which plants convert sunlight into energy.",
        expected_output=None,
        context=[
            "Plants use chlorophyll to capture light.",
            "Carbon dioxide and water are needed for photosynthesis.",
        ],
    )

    print(f"Score: {result.score}")
    print(f"Details: {result.details}")


def example_with_anthropic_model():
    """Example using Anthropic model (requires ANTHROPIC_API_KEY env var)."""

    model_config = {
        "type": "anthropic",
        "model_name": "claude-3-sonnet-20240229",
        # API key will be read from ANTHROPIC_API_KEY environment variable
    }

    metric = DeepEvalAnswerRelevancy(threshold=0.8, model_config=model_config)

    result = metric.evaluate(
        input="What are the benefits of exercise?",
        output="Exercise improves cardiovascular health, strengthens muscles, and enhances mental "
        "well-being.",
        expected_output="Exercise has many health benefits including better heart health and mood.",
        context=[
            "Regular exercise is important for health.",
            "Physical activity can reduce stress and anxiety.",
        ],
    )

    print(f"Score: {result.score}")
    print(f"Details: {result.details}")


def example_with_azure_openai():
    """Example using Azure OpenAI
    (requires AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT env vars)."""

    model_config = {
        "type": "azure_openai",
        "model_name": "gpt-4",
        "extra_params": {
            # "azure_endpoint": "https://your-resource.openai.azure.com/",
            # or use AZURE_OPENAI_ENDPOINT env var
            "api_version": "2024-02-15-preview",
        },
    }

    metric = DeepEvalFaithfulness(threshold=0.7, model_config=model_config)

    result = metric.evaluate(
        input="Explain machine learning.",
        output="Machine learning is a subset of AI that enables computers to learn from data.",
        expected_output=None,
        context=[
            "AI stands for artificial intelligence.",
            "Machine learning algorithms improve with experience.",
        ],
    )

    print(f"Score: {result.score}")
    print(f"Details: {result.details}")


def example_with_ollama():
    """Example using Ollama for local models."""

    model_config = {
        "type": "ollama",
        "model_name": "llama2",
        "extra_params": {
            # "base_url": "http://localhost:11434"  # or use OLLAMA_BASE_URL env var
        },
    }

    metric = DeepEvalContextualRelevancy(threshold=0.6, model_config=model_config)

    result = metric.evaluate(
        input="What is blockchain?",
        output="Blockchain is a distributed ledger technology that ensures data integrity.",
        expected_output=None,
        context=[
            "Blockchain uses cryptographic hashing.",
            "It's the technology behind cryptocurrencies.",
        ],
    )

    print(f"Score: {result.score}")
    print(f"Details: {result.details}")


def example_with_custom_api_key():
    """Example providing API key directly instead of using environment variables."""

    model_config = {
        "type": "gemini",
        "model_name": "gemini-1.5-pro",
        "api_key": "your-direct-api-key-here",
    }

    metric = DeepEvalAnswerRelevancy(threshold=0.8, model_config=model_config)  # noqa: F841

    # Note: This won't actually work without a real API key
    print("This example shows how to provide API key directly in config")


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

    example_with_custom_api_key()
    example_future_database_config()
