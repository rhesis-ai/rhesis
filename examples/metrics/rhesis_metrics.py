from rhesis.sdk.metrics.constants import ThresholdOperator
from rhesis.sdk.metrics.providers.native.prompt_metric_categorical import (
    # Example usage of RhesisPromptMetricCategorical
    CategoricalJudge,
)
from rhesis.sdk.metrics.providers.native.prompt_metric_numeric import (
    NumericJudge,
)

if __name__ == "__main__":
    print("Example: Creating a categorical metric for evaluating response quality")

    # Create a categorical metric for evaluating response quality
    metric = CategoricalJudge(
        name="response_quality_evaluator",
        evaluation_prompt=(
            "Evaluate the quality of the response based on accuracy, completeness, and helpfulness."
        ),
        evaluation_steps=(
            "1. Check if the response directly answers the question\n"
            "2. Verify the information is accurate\n"
            "3. Assess if the response is complete and helpful"
        ),
        reasoning=(
            "A good response should be accurate, complete, and directly "
            "address the user's question."
        ),
        categories=["poor", "fair", "good", "perfect"],
        passing_categories=[
            "good",
            "perfect",
        ],  # Only "good" and "perfect" are considered passing
        evaluation_examples=(
            "Example: Question: 'What is Python?' "
            "Good response: 'Python is a programming language...' "
            "Poor response: 'I don't know.'"
        ),
        model="gemini",  # Optional: specify the model to use
    )

    # Example evaluation
    input_query = "What is machine learning?"
    system_output = (
        "Machine learning is a subset of artificial intelligence that enables computers to "
        "learn and improve from experience without being explicitly programmed."
    )
    expected_output = (
        "Machine learning is a field of AI that focuses on algorithms that can learn from data."
    )

    # Evaluate the response
    result = metric.evaluate(
        input=input_query,
        output=system_output,
        expected_output=expected_output,
        context=["AI and machine learning concepts", "Computer science fundamentals"],
    )

    print(result)

    print("--------------------------------")
    print("--------------------------------")

    """
    Example usage of RhesisPromptMetricNumeric for evaluating text quality.
    
    This example demonstrates how to create and use a numeric prompt metric
    to evaluate the quality of generated text responses.
    """

    # Create a metric for evaluating answer quality
    metric = NumericJudge(
        name="answer_quality_evaluator",
        evaluation_prompt="""
        Evaluate the quality of the provided answer based on the following criteria:
        1. Accuracy: How correct and factual is the information?
        2. Completeness: Does it fully address the question?
        3. Clarity: Is the answer clear and well-structured?
        4. Relevance: How relevant is the answer to the question asked?
        """,
        evaluation_steps="""
        1. Read the question and the provided answer carefully
        2. Check the answer against the expected output for accuracy
        3. Assess completeness by checking if all aspects of the question are addressed
        4. Evaluate clarity and structure of the response
        5. Determine overall relevance to the original question
        6. Assign a score from 0.0 to 1.0 based on these criteria
        """,
        reasoning="""
        Consider the context provided and compare the answer with the expected output.
        A perfect answer (1.0) should be completely accurate, fully address the question,
        be clearly written, and highly relevant. Lower scores should reflect deficiencies
        in any of these areas.
        """,
        evaluation_examples="""
        Example 1:
        Question: "What is the capital of France?"
        Answer: "Paris"
        Expected: "The capital of France is Paris"
        Score: 0.9 (accurate but not complete)
        
        Example 2:
        Question: "What is the capital of France?"
        Answer: "The capital of France is Paris, located in the north-central part of the country."
        Expected: "The capital of France is Paris"
        Score: 1.0 (accurate, complete, and well-structured)
        """,
        min_score=0.0,
        max_score=1.0,
        threshold=0.7,  # 70% threshold for success
        threshold_operator=ThresholdOperator.GREATER_THAN_OR_EQUAL,
        model="gemini",
    )

    # Example data for evaluation
    test_input = "What are the main benefits of renewable energy?"
    test_output = (
        "Renewable energy sources like solar and wind power are clean, sustainable, "
        "and help reduce greenhouse gas emissions. They also create jobs and reduce "
        "dependence on fossil fuels."
    )
    expected_output = (
        "The main benefits of renewable energy include: 1) Environmental benefits - "
        "reduced greenhouse gas emissions and air pollution, 2) Economic benefits - "
        "job creation and energy cost savings, 3) Energy security - reduced "
        "dependence on foreign fossil fuels, 4) Sustainability - inexhaustible "
        "energy sources"
    )

    result = metric.evaluate(input=test_input, output=test_output, expected_output=expected_output)

    print(f"Score: {result.score}")
    print(f"Is Successful: {result.details['is_successful']}")
    print(f"Reason: {result.details['reason']}")
    print(f"Threshold: {result.details['threshold']}")
    print(f"Score Range: {result.details['min_score']} - {result.details['max_score']}")
