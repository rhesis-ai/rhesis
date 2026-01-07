from dataclasses import fields
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import create_model

from rhesis.sdk.metrics.base import MetricResult, MetricScope, MetricType, ScoreType
from rhesis.sdk.metrics.providers.native.base import JudgeBase
from rhesis.sdk.metrics.providers.native.configs import CategoricalJudgeConfig
from rhesis.sdk.models.base import BaseLLM

METRIC_TYPE = MetricType.RAG
SCORE_TYPE = ScoreType.CATEGORICAL


class CategoricalJudge(JudgeBase):
    """
    A generic metric that evaluates outputs based on a custom prompt template.
    Uses LLM to perform evaluation based on provided evaluation criteria.
    """

    def __init__(
        self,
        categories: Optional[List[str]] = None,
        passing_categories: Optional[Union[str, List[str]]] = None,
        evaluation_steps: Optional[str] = None,
        reasoning: Optional[str] = None,
        evaluation_examples: Optional[str] = None,
        evaluation_prompt: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        model: Optional[Union[BaseLLM, str]] = None,
        requires_ground_truth: bool = True,
        requires_context: bool = False,
        metric_scope: Optional[List[Union[str, "MetricScope"]]] = None,
    ):
        # Set default metric_scope to both Single-Turn and Multi-Turn if not provided
        if metric_scope is None:
            metric_scope = [MetricScope.SINGLE_TURN, MetricScope.MULTI_TURN]
        """
        Initialize the categorical prompt metric.

        Args:
            name (str): Unique name for this metric instance
            evaluation_prompt (str): The main evaluation criteria and instructions for the LLM
            evaluation_steps (str): Step-by-step process the LLM should follow for evaluation
            reasoning (str): Guidelines for the LLM's reasoning process during evaluation
            categories (List[str]): List of valid categories the LLM can return.
                Must contain at least 2 scores.
            passing_categories (Union[str, List[str]]): Category(s) considered successful/passing.
                Can be a single string or list of strings. All values must be present in
                categories.
            evaluation_examples (str, optional): Examples to guide the LLM's evaluation.
                Defaults to empty string.
            model (Optional[str], optional): The LLM model to use for evaluation.
                If None, uses the default model. Defaults to None.
            requires_ground_truth (bool, optional): Whether this metric requires ground truth
                for evaluation. Defaults to True.
            requires_context (bool, optional): Whether this metric requires context chunks
                for evaluation. Defaults to False.
            metric_scope (Optional[List[Union[str, MetricScope]]], optional): Scope(s) where
                this metric applies. Can be ["Single-Turn"], ["Multi-Turn"], or both.
                Defaults to both Single-Turn and Multi-Turn if not specified.

        Raises:
            ValueError: If categories has fewer than 2 items
            ValueError: If passing_categories is not a string or list
            ValueError: If passing_categories contains values not in categories
            ValueError: If the number of passing_categories exceeds categories
        """
        self.config = CategoricalJudgeConfig(
            categories=categories,
            passing_categories=passing_categories,
            evaluation_steps=evaluation_steps,
            reasoning=reasoning,
            evaluation_examples=evaluation_examples,
            evaluation_prompt=evaluation_prompt,
            name=name,
            description=description,
            score_type=SCORE_TYPE,
            metric_type=METRIC_TYPE,
            requires_ground_truth=requires_ground_truth,
            requires_context=requires_context,
            metric_scope=metric_scope,
            class_name=self.__class__.__name__,
        )

        super().__init__(config=self.config, model=model)

        self.categories = self.config.categories
        self.passing_categories = self.config.passing_categories

        # Set up Jinja environment
        self._setup_jinja_environment()

    def _get_prompt_template(
        self,
        input: str,
        output: str,
        expected_output: str,
        context: Optional[List[str]] = None,
        **additional_template_vars,
    ) -> str:
        """
        Generate the prompt to be sent to the LLM using a Jinja template.

        This method uses the base class implementation with categorical-specific template variables.

        Args:
            input (str): The input query/question
            output (str): The system output/response
            expected_output (str): The expected or reference output
            context (Optional[List[str]], optional): List of context chunks used for the response.
                Defaults to None.

        Returns:
            str: The rendered prompt template ready to be sent to the LLM
        """
        return super()._get_prompt_template(
            input=input,
            output=output,
            expected_output=expected_output,
            context=context,
            categories=self.categories,
            passing_categories=self.passing_categories,
        )

    def evaluate(
        self,
        input: str,
        output: str,
        expected_output: Optional[str],
        context: Optional[List[str]] = None,
    ) -> MetricResult:
        """
        Evaluate the output using the LLM with the custom prompt template.

        This method generates a comprehensive evaluation prompt using the Jinja2 template
        system, sends it to the configured LLM, and returns a structured result with the
        categorical score and detailed evaluation information.

        Args:
            input (str): The input query/question that was posed to the system
            output (str): The system's response/output that needs to be evaluated
            expected_output (Optional[str]): The expected or reference output (ground truth).
                Required for this metric as it requires ground truth for evaluation.
            context (Optional[List[str]], optional): List of context chunks used for the response.
                Defaults to None.

        Returns:
            MetricResult: The evaluation result containing:
                - score (str): The categorical score returned by the LLM (one of categories)
                - details (Dict[str, Any]): Detailed evaluation information including:
                    - score: The categorical score
                    - score_type: "categorical"
                    - prompt: The full evaluation prompt sent to the LLM
                    - reason: The LLM's reasoning for the score
                    - is_successful: Whether the score meets the success criteria
                    - categories: List of valid categories
                    - passing_categories: List of passing categories
                    - error: Error message if evaluation failed
                    - exception_type: Type of exception if evaluation failed
                    - exception_details: Detailed exception information if evaluation failed

        Raises:
            ValueError: If input is empty or not a string
            ValueError: If output is not a string
            ValueError: If expected_output is None (this metric requires ground truth)
            ValueError: If context is provided but not a list
            ValueError: If template rendering fails
            ValueError: If LLM response validation fails

        Note:
            The method handles various error conditions gracefully, returning error scores
            with detailed information rather than raising exceptions for LLM-related issues.
            Only input validation errors are raised as exceptions.
        """
        # Validate inputs using shared method
        self._validate_evaluate_inputs(input, output, expected_output, context)

        # Generate the evaluation prompt
        prompt = self._get_prompt_template(input, output, expected_output or "", context or [])

        # Initialize common details fields
        details = self._get_base_details(prompt)
        details.update(
            {
                "categories": self.categories,
                "passing_categories": self.passing_categories,
            }
        )

        try:
            # Run the evaluation with structured response model
            # Create a proper Literal type from the possible scores
            if len(self.categories) == 1:
                score_literal = Literal[self.categories[0]]
            else:
                # Create individual string literals - use a more compatible approach
                score_literal = Literal[tuple(self.categories)]

            ScoreResponseCategorical = create_model(
                "ScoreResponseCategorical", score=(score_literal, ...), reason=(str, ...)
            )
            response = self.model.generate(prompt, schema=ScoreResponseCategorical)
            response = ScoreResponseCategorical(**response)  # type: ignore[arg-type]

            # Get the score directly from the response
            score = response.score  # type: ignore[attr-defined]
            reason = response.reason  # type: ignore[attr-defined]

            # Check if the evaluation meets the reference score using the base class method
            is_successful = self._evaluate_score(
                score=score,
                passing_categories=self.passing_categories,  # type: ignore[arg-type]§
            )

            # Update details with success-specific fields
            details.update(
                {
                    "score": score,
                    "reason": reason,
                    "is_successful": is_successful,
                }
            )

            return MetricResult(score=score, details=details)

        except Exception as e:
            return self._handle_evaluation_error(e, details, "error")

    def _evaluate_score(self, score: str, passing_categories: List[str]) -> bool:
        """
        Evaluate if a score meets the success criteria for categorical metrics.

        This method checks if the provided score is present in the list of passing categories.

        Args:
            score (str): The score to evaluate
            passing_categories (List[str]): List of categories considered passing

        Returns:
            bool: True if the score is in passing_categories, False otherwise
        """
        result = score in passing_categories
        return result

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "CategoricalJudge":
        """Create a metric from a dictionary."""
        # Get all field names from the dataclass
        valid_fields = {field.name for field in fields(CategoricalJudgeConfig)}

        # Filter config to only include keys that exist in the dataclass
        filtered_config = {k: v for k, v in config.items() if k in valid_fields}

        return cls.from_config(CategoricalJudgeConfig(**filtered_config))
