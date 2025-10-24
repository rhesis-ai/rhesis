import json
import os
from typing import Any, List, Optional, Union

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field

from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.metrics.base import MetricResult, retry_evaluation
from rhesis.backend.metrics.rhesis.metric_base import RhesisMetricBase, ScoreType, ThresholdOperator


class ScoreResponse(BaseModel):
    """Model for structured score response from LLM evaluation."""

    score: Union[float, str, int] = Field(description="Evaluation score")
    reason: str = Field(description="Explanation for the score", default="")


class RhesisPromptMetric(RhesisMetricBase):
    """
    A generic metric that evaluates outputs based on a custom prompt template.
    Uses LLM to perform evaluation based on provided evaluation criteria.
    """

    def __init__(
        self,
        name: str,
        evaluation_prompt: str,
        evaluation_steps: str,
        reasoning: str,
        evaluation_examples: str = "",
        score_type: Union[ScoreType, str] = ScoreType.NUMERIC,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        threshold: Optional[float] = None,
        reference_score: Optional[str] = None,
        threshold_operator: Union[ThresholdOperator, str] = None,
        provider: str = "gemini",
        model: Optional[Union[str, Any]] = None,
        api_key: Optional[str] = None,
        metric_type="rag",
        **kwargs,
    ):
        from rhesis.backend.app.constants import DEFAULT_GENERATION_MODEL, DEFAULT_MODEL_NAME

        # Store the model instance if it's a BaseLLM
        self.model_instance = None

        # Handle model parameter - can be BaseLLM instance, string, or None
        if model and not isinstance(model, str):
            # It's a BaseLLM instance - store it and extract configuration
            logger.debug(f"[METRIC_INIT] Using BaseLLM instance for metric '{name}'")
            self.model_instance = model
            # Extract provider from model_name (format: "provider/model-name")
            if hasattr(model, "model_name") and "/" in model.model_name:
                self.provider = model.model_name.split("/")[0]
                self.model = model.model_name.split("/")[1]
            else:
                self.provider = provider
                self.model = getattr(model, "model_name", None) or DEFAULT_MODEL_NAME
            self.api_key = (
                getattr(model, "api_key", None) or api_key or os.environ.get("GEMINI_API_KEY")
            )
            logger.debug(
                f"[METRIC_INIT] Extracted from BaseLLM: provider={self.provider}, model={self.model}"
            )
        elif isinstance(model, str):
            # It's a provider name string - will use SDK to create model
            logger.debug(f"[METRIC_INIT] Using provider string '{model}' for metric '{name}'")
            self.provider = model
            self.api_key = (
                api_key
                or os.environ.get(f"{model.upper()}_API_KEY")
                or os.environ.get("GEMINI_API_KEY")
            )
            self.model = (
                os.environ.get(f"{model.upper()}_MODEL_NAME")
                or os.environ.get("GEMINI_MODEL_NAME")
                or DEFAULT_MODEL_NAME
            )
        else:
            # Use defaults from constants
            logger.debug(f"[METRIC_INIT] Using default model for metric '{name}'")
            self.provider = provider or DEFAULT_GENERATION_MODEL
            self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
            self.model = os.environ.get("GEMINI_MODEL_NAME") or DEFAULT_MODEL_NAME

        # Convert string to enum if needed
        if isinstance(score_type, str):
            score_type = ScoreType(score_type)
        if isinstance(threshold_operator, str):
            threshold_operator = ThresholdOperator(threshold_operator)

        self.score_type = score_type
        self.threshold_operator = threshold_operator

        # Handle different score types
        if score_type == ScoreType.NUMERIC:
            # For numeric scores, we need min_score, max_score, and threshold
            self.min_score = min_score if min_score is not None else 1.0
            self.max_score = max_score if max_score is not None else 5.0

            # Handle threshold based on whether it's raw or normalized
            if threshold is None:
                threshold = 0.5  # Default normalized threshold

            normalized_threshold = threshold
            if 0 <= threshold <= 1:
                # This is already a normalized threshold
                normalized_threshold = threshold
            elif self.min_score <= threshold <= self.max_score:
                # This is a raw threshold, convert to normalized
                normalized_threshold = (threshold - self.min_score) / (
                    self.max_score - self.min_score
                )
            else:
                # Invalid threshold
                raise ValueError(
                    f"Threshold must be either between 0 and 1 (normalized) or between {self.min_score} and {self.max_score} (raw)"
                )
            # Pass the normalized threshold to the base class
            super().__init__(
                name=name,
                threshold=normalized_threshold,
                reference_score=None,
                metric_type=metric_type,
            )
            # Store original threshold for reporting
            self.raw_threshold = threshold

        else:  # BINARY or CATEGORICAL
            # For binary/categorical scores, we use reference_score instead of threshold
            if reference_score is None:
                if score_type == ScoreType.BINARY:
                    reference_score = "true"  # Default reference for binary
                else:  # CATEGORICAL
                    raise ValueError("reference_score is required for categorical score type")

            # min_score and max_score are not relevant for binary/categorical
            self.min_score = None
            self.max_score = None

            # Pass reference_score to the base class, threshold is None
            super().__init__(
                name=name, threshold=None, reference_score=reference_score, metric_type=metric_type
            )
            self.raw_threshold = None

        # Store other parameters
        self.evaluation_prompt = evaluation_prompt
        self.evaluation_steps = evaluation_steps
        self.reasoning = reasoning
        self.evaluation_examples = evaluation_examples
        self.provider = provider

        # Store additional parameters for future use
        self.additional_params = kwargs.copy()

        # Set up Jinja environment
        templates_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates"
        )
        self.jinja_env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    @property
    def requires_ground_truth(self) -> bool:
        """This metric typically requires ground truth."""
        return True

    def get_prompt_template(
        self, input: str, output: str, expected_output: str, context: List[str] = None
    ) -> str:
        """
        Generate the prompt to be sent to the LLM using a Jinja template.
        """
        context_text = "\n".join(context) if context else "No context provided."

        # Load the template
        template = self.jinja_env.get_template("prompt_metric.jinja")

        # Prepare template variables based on score type
        template_vars = {
            "evaluation_prompt": self.evaluation_prompt,
            "evaluation_steps": self.evaluation_steps,
            "reasoning": self.reasoning,
            "evaluation_examples": self.evaluation_examples,
            "input": input,
            "context_text": context_text,
            "expected_output": expected_output,
            "output": output,
            "score_type": self.score_type.value,
        }

        # Add score type specific variables
        if self.score_type == ScoreType.NUMERIC:
            template_vars.update(
                {
                    "min_score": self.min_score,
                    "max_score": self.max_score,
                }
            )
        # For binary and categorical, no additional variables needed

        # Render the template with all required variables
        prompt = template.render(**template_vars)

        return prompt

    def run_evaluation(self, prompt: str) -> ScoreResponse:
        """
        Run the evaluation using the model instance directly.
        Returns a ScoreResponse with score and reason.
        """
        # Use the BaseLLM instance if available, otherwise create one from SDK
        if self.model_instance:
            model_to_use = self.model_instance
            logger.debug("[METRIC_EVAL] Using stored BaseLLM instance")
        else:
            # Create model instance from SDK
            from rhesis.sdk.models.factory import get_model

            logger.debug(
                f"[METRIC_EVAL] Creating model from SDK: provider={self.provider}, model={self.model}"
            )
            model_to_use = get_model(
                provider=self.provider, model_name=self.model, api_key=self.api_key
            )

        # Add JSON formatting instruction to the prompt
        json_prompt = f"""{prompt}

IMPORTANT: You must respond with ONLY a valid JSON object in this exact format:
{{
  "score": <your_score>,
  "reason": "<your_explanation>"
}}

Do not include any other text before or after the JSON object."""

        # Call the model directly
        response_text = model_to_use.generate(json_prompt)

        # Parse the JSON response
        try:
            # Try to extract JSON from the response (handle cases where model adds extra text)
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                response_dict = json.loads(json_text)
                return ScoreResponse(**response_dict)
            else:
                raise ValueError(f"No JSON object found in response: {response_text}")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"[METRIC_EVAL] Failed to parse JSON response: {e}")
            logger.error(f"[METRIC_EVAL] Raw response: {response_text}")
            # Return a fallback response
            return ScoreResponse(score=0.0, reason=f"Failed to parse model response: {str(e)}")

    def _process_score(self, raw_score: Union[float, str, int]) -> Union[float, str]:
        """
        Process the raw score based on the score type.

        Args:
            raw_score: The raw score from the LLM

        Returns:
            Union[float, str]: Processed score
        """
        if self.score_type == ScoreType.NUMERIC:
            # For numeric scores, ensure it's a float and within range
            try:
                score = float(raw_score)
                return max(min(score, self.max_score), self.min_score)
            except (ValueError, TypeError):
                return self.min_score

        elif self.score_type == ScoreType.BINARY:
            # For binary scores, convert to standardized string representation
            if isinstance(raw_score, str):
                raw_score = raw_score.lower().strip()
                if raw_score in ["true", "yes", "1", "pass", "success", "correct"]:
                    return "true"
                else:
                    return "false"
            elif isinstance(raw_score, (int, float)):
                return "true" if raw_score > 0 else "false"
            elif isinstance(raw_score, bool):
                return "true" if raw_score else "false"
            else:
                return "false"

        elif self.score_type == ScoreType.CATEGORICAL:
            # For categorical scores, return as string
            return str(raw_score).strip()

        return str(raw_score)

    @retry_evaluation(
        retry_exceptions=(
            ConnectionError,
            TimeoutError,
            Exception,
        )  # Using broader Exception to catch LLM API errors
    )
    def evaluate(
        self, input: str, output: str, expected_output: Optional[str], context: List[str] = None
    ) -> MetricResult:
        """
        Evaluate the output using the LLM with the custom prompt template.

        Args:
            input: The input query/question
            output: The system output/response
            expected_output: The expected or reference output (ground truth)
            context: List of context chunks used for the response

        Returns:
            MetricResult: The evaluation result
        """
        if expected_output is None and self.requires_ground_truth:
            raise ValueError(f"{self.name} metric requires ground truth but none was provided")

        # Check for empty or whitespace-only output and return score of 0 immediately
        if not output or not output.strip():
            reason = "Empty or whitespace-only output provided. Score set to minimum value."

            # Prepare details for empty output
            details = {
                "raw_score": self.min_score,
                "processed_score": self.min_score,
                "score_type": self.score_type.value,
                "llm_response": "Not evaluated - empty output detected",
                "prompt": "Not generated - empty output detected",
                "reason": reason,
                "is_successful": False,  # Empty outputs are always unsuccessful
                "threshold_operator": self.threshold_operator.value
                if self.threshold_operator
                else None,
                "empty_output_detected": True,
            }

            # Add score type specific details
            if self.score_type == ScoreType.NUMERIC:
                raw_threshold = getattr(self, "raw_threshold", self.threshold)
                details.update(
                    {
                        "final_score": self.min_score,
                        "min_score": self.min_score,
                        "max_score": self.max_score,
                        "threshold": raw_threshold,
                        "normalized_threshold": self.threshold,
                        "raw_threshold": raw_threshold,
                    }
                )
                return MetricResult(score=self.min_score, details=details)
            else:  # BINARY or CATEGORICAL
                details.update(
                    {
                        "reference_score": self.reference_score,
                    }
                )
                if self.score_type == ScoreType.BINARY:
                    return MetricResult(score="false", details=details)
                else:  # CATEGORICAL
                    return MetricResult(score="error", details=details)

        # Generate the evaluation prompt
        prompt = self.get_prompt_template(input, output, expected_output or "", context or [])

        try:
            # Run the evaluation using the model directly
            response = self.run_evaluation(prompt)

            # Get the score and process it based on score type
            raw_score = response.score
            processed_score = self._process_score(raw_score)
            reason = (
                response.reason
                if hasattr(response, "reason") and response.reason
                else f"Score: {raw_score}"
            )

            # Handle evaluation based on score type
            if self.score_type == ScoreType.NUMERIC:
                # For numeric scores, use the processed score directly (no normalization)
                evaluation_score = processed_score

                # Use raw threshold for comparison with raw scores (no normalization)
                raw_threshold = getattr(self, "raw_threshold", self.threshold)

                # Check if the evaluation meets the threshold using the base class method
                is_successful = self.evaluate_score(
                    score=evaluation_score,
                    score_type=self.score_type,
                    threshold=raw_threshold,
                    threshold_operator=self.threshold_operator,
                )

            else:  # BINARY or CATEGORICAL
                # For binary/categorical scores, use the processed score directly
                evaluation_score = processed_score

                # Check if the evaluation meets the reference score using the base class method
                is_successful = self.evaluate_score(
                    score=evaluation_score,
                    score_type=self.score_type,
                    reference_score=self.reference_score,
                    threshold_operator=self.threshold_operator,
                )

            # Get the original LLM response content for debugging
            llm_response_content = f"Score: {raw_score}, Reason: {reason}"

            # Prepare details based on score type
            details = {
                "raw_score": raw_score,
                "processed_score": processed_score,
                "score_type": self.score_type.value,
                "llm_response": llm_response_content,
                "prompt": prompt,
                "reason": reason,
                "is_successful": is_successful,
                "threshold_operator": self.threshold_operator.value
                if self.threshold_operator
                else None,
            }

            # Add score type specific details
            if self.score_type == ScoreType.NUMERIC:
                raw_threshold = getattr(self, "raw_threshold", self.threshold)
                details.update(
                    {
                        "final_score": evaluation_score,  # Raw score (not normalized)
                        "min_score": self.min_score,
                        "max_score": self.max_score,
                        "threshold": raw_threshold,  # Raw threshold for comparison
                        "normalized_threshold": self.threshold,  # Keep for reference
                        "raw_threshold": raw_threshold,
                    }
                )
            else:  # BINARY or CATEGORICAL
                details.update(
                    {
                        "reference_score": self.reference_score,
                    }
                )

            return MetricResult(score=evaluation_score, details=details)

        except Exception as e:
            # Log the error for debugging with full traceback
            import traceback

            from rhesis.backend.logging.rhesis_logger import logger

            error_msg = f"Error evaluating with {self.name}: {str(e)}"
            logger.error(f"Exception in RhesisPromptMetric.evaluate: {error_msg}")
            logger.error(f"Provider: {self.provider}, Model: {self.model}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Exception details: {str(e)}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")

            # Return a fallback score with error information
            details = {
                "error": error_msg,
                "reason": error_msg,
                "exception_type": type(e).__name__,
                "exception_details": str(e),
                "provider": self.provider,
                "model": self.model,
                "prompt": prompt,
                "score_type": self.score_type.value,
                "threshold_operator": self.threshold_operator.value
                if self.threshold_operator
                else None,
            }

            # Add score type specific details
            if self.score_type == ScoreType.NUMERIC:
                raw_threshold = getattr(self, "raw_threshold", self.threshold)
                details.update(
                    {
                        "min_score": self.min_score,
                        "max_score": self.max_score,
                        "threshold": raw_threshold,  # Use raw threshold for consistency
                        "normalized_threshold": self.threshold,
                        "raw_threshold": raw_threshold,
                    }
                )
                # Return a default minimal score for numeric
                return MetricResult(score=0.0, details=details)
            else:  # BINARY or CATEGORICAL
                details.update(
                    {
                        "reference_score": self.reference_score,
                    }
                )
                # Return a default failure score for binary/categorical
                if self.score_type == ScoreType.BINARY:
                    return MetricResult(score="false", details=details)
                else:  # CATEGORICAL
                    return MetricResult(score="error", details=details)
