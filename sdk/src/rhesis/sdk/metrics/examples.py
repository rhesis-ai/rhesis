"""
Examples of using metrics of different frameworks.
"""

from rhesis.sdk.metrics.providers.deepeval.metrics import (
    DeepEvalAnswerRelevancy,
    DeepEvalFaithfulness,
)
from rhesis.sdk.models.factory import get_model


def deepeval_with_default_model():
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
def deepeval_with_future_database_config():
    """
    Example of how this could work with database configuration in the future.

    """

    # This would come from your database
    model_config_from_database = {
        "provider": "rhesis",
        "model_name": "gpt-4-turbo",
    }
    model = get_model(model_config_from_database)

    metric = DeepEvalFaithfulness(threshold=0.8, model=model)  # noqa: F841

    print("This example shows how database config could work in the future")


def deepeval_with_gemini_model():
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
    from rhesis.sdk.models.factory import ModelConfig
    # print("DeepEval Metrics with Multiple Models - Examples")
    # print("=" * 50)
    # deepeval_with_default_model()
    # print("=" * 50)
    # deepeval_with_gemini_model()
    # print("=" * 50)
    # deepeval_with_future_database_config()
    # print("=" * 50)

    model_config_from_database = {
        "provider": "rhesis",
        "model_name": "gpt-4-turbo",
    }
    model_config_from_database = ModelConfig(**model_config_from_database)
    print(model_config_from_database)
    model = get_model(config=model_config_from_database)

    metric = DeepEvalFaithfulness(threshold=0.8, model=model)  # noqa: F841
    result = metric.evaluate(
        input="What is the capital of France?",
        output="The capital of France is Paris.",
        expected_output="Paris",
        context=["France is a country in Europe.", "Paris is the largest city in France."],
    )
    print(f"Score: {result.score}")
    print(f"Details: {result.details}")
