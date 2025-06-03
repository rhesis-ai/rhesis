from typing import Dict, List, Any, Optional, Union
import os
from jinja2 import Environment, FileSystemLoader, select_autoescape

from mirascope import llm
from pydantic import BaseModel, Field

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
        provider: str = "openai",
        model: str = "gpt-4o",
        metric_type="rag",
        **kwargs
    ):
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
                normalized_threshold = (threshold - self.min_score) / (self.max_score - self.min_score)
            else:
                # Invalid threshold
                raise ValueError(
                    f"Threshold must be either between 0 and 1 (normalized) or between {self.min_score} and {self.max_score} (raw)"
                )
            # Pass the normalized threshold to the base class
            super().__init__(name=name, threshold=normalized_threshold, reference_score=None, metric_type=metric_type)
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
            super().__init__(name=name, threshold=None, reference_score=reference_score, metric_type=metric_type)
            self.raw_threshold = None
        
        # Store other parameters
        self.evaluation_prompt = evaluation_prompt
        self.evaluation_steps = evaluation_steps
        self.reasoning = reasoning
        self.evaluation_examples = evaluation_examples
        self.provider = provider
        self.model = model
        self.additional_params = kwargs
        
        # Set up Jinja environment
        templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
        self.jinja_env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )

    @property
    def requires_ground_truth(self) -> bool:
        """This metric typically requires ground truth."""
        return True

    def get_prompt_template(self, input: str, output: str, expected_output: str, context: List[str] = None) -> str:
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
            "score_type": self.score_type.value
        }
        
        # Add score type specific variables
        if self.score_type == ScoreType.NUMERIC:
            template_vars.update({
                "min_score": self.min_score,
                "max_score": self.max_score,
            })
        # For binary and categorical, no additional variables needed
        
        # Render the template with all required variables
        prompt = template.render(**template_vars)
        
        return prompt

    @llm.call(provider="provider_placeholder", model="model_placeholder", response_model=ScoreResponse)
    def run_evaluation(self, prompt: str) -> str:
        """
        Run the evaluation using Mirascope LLM call with structured response model.
        This function will be decorated with the actual provider and model at runtime.
        """
        return prompt

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
                if raw_score in ['true', 'yes', '1', 'pass', 'success', 'correct']:
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
        retry_exceptions=(ConnectionError, TimeoutError, Exception)  # Using broader Exception to catch LLM API errors
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
        
        # Generate the evaluation prompt
        prompt = self.get_prompt_template(input, output, expected_output or "", context or [])
        
        # Override the provider and model at runtime
        evaluation_fn = llm.override(
            self.run_evaluation,
            provider=self.provider,
            model=self.model,
            call_params=self.additional_params
        )
        
        try:
            # Run the evaluation with structured response model
            response = evaluation_fn(prompt)
            
            # Get the score and process it based on score type
            raw_score = response.score
            processed_score = self._process_score(raw_score)
            reason = response.reason if hasattr(response, 'reason') and response.reason else f"Score: {raw_score}"
            
            # Handle evaluation based on score type
            if self.score_type == ScoreType.NUMERIC:
                # For numeric scores, normalize the score and use threshold
                normalized_score = (processed_score - self.min_score) / (self.max_score - self.min_score)
                evaluation_score = normalized_score
                
                # Check if the evaluation meets the threshold using the base class method
                is_successful = self.evaluate_score(
                    score=evaluation_score,
                    score_type=self.score_type,
                    threshold=self.threshold,
                    threshold_operator=self.threshold_operator
                )
                
            else:  # BINARY or CATEGORICAL
                # For binary/categorical scores, use the processed score directly
                evaluation_score = processed_score
                
                # Check if the evaluation meets the reference score using the base class method
                is_successful = self.evaluate_score(
                    score=evaluation_score,
                    score_type=self.score_type,
                    reference_score=self.reference_score,
                    threshold_operator=self.threshold_operator
                )
            
            # Get the original LLM response content for debugging
            llm_response_content = str(response._response.content) if hasattr(response, '_response') else "No raw response available"
            
            # Prepare details based on score type
            details = {
                "raw_score": raw_score,
                "processed_score": processed_score,
                "score_type": self.score_type.value,
                "llm_response": llm_response_content,
                "prompt": prompt,
                "reason": reason,
                "is_successful": is_successful,
                "threshold_operator": self.threshold_operator.value if self.threshold_operator else None,
            }
            
            # Add score type specific details
            if self.score_type == ScoreType.NUMERIC:
                details.update({
                    "normalized_score": evaluation_score,
                    "min_score": self.min_score,
                    "max_score": self.max_score,
                    "threshold": self.threshold,
                    "raw_threshold": getattr(self, "raw_threshold", self.threshold)
                })
            else:  # BINARY or CATEGORICAL
                details.update({
                    "reference_score": self.reference_score,
                })
            
            return MetricResult(score=evaluation_score, details=details)
            
        except Exception as e:
            # Log the error for debugging
            error_msg = f"Error evaluating with {self.name}: {str(e)}"
            # Return a fallback score with error information
            details = {
                "error": error_msg,
                "prompt": prompt,
                "score_type": self.score_type.value,
                "threshold_operator": self.threshold_operator.value if self.threshold_operator else None,
            }
            
            # Add score type specific details
            if self.score_type == ScoreType.NUMERIC:
                details.update({
                    "min_score": self.min_score,
                    "max_score": self.max_score,
                    "threshold": self.threshold,
                    "raw_threshold": getattr(self, "raw_threshold", self.threshold)
                })
                # Return a default minimal score for numeric
                return MetricResult(score=0.0, details=details)
            else:  # BINARY or CATEGORICAL
                details.update({
                    "reference_score": self.reference_score,
                })
                # Return a default failure score for binary/categorical
                if self.score_type == ScoreType.BINARY:
                    return MetricResult(score="false", details=details)
                else:  # CATEGORICAL
                    return MetricResult(score="error", details=details) 