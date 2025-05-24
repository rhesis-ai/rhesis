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
        min_score: float = 1.0,
        max_score: float = 5.0,
        threshold: float = 0.5,
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
        
        # Store the score range (only relevant for numeric scores)
        self.min_score = min_score
        self.max_score = max_score
        
        # Handle threshold based on score type
        if score_type == ScoreType.NUMERIC:
            # Validate threshold based on whether it's raw or normalized
            normalized_threshold = threshold
            if 0 <= threshold <= 1:
                # This is already a normalized threshold
                normalized_threshold = threshold
            elif min_score <= threshold <= max_score:
                # This is a raw threshold, convert to normalized
                normalized_threshold = (threshold - min_score) / (max_score - min_score)
            else:
                # Invalid threshold
                raise ValueError(
                    f"Threshold must be either between 0 and 1 (normalized) or between {min_score} and {max_score} (raw)"
                )
            # Pass the normalized threshold to the base class
            super().__init__(name=name, threshold=normalized_threshold, metric_type=metric_type)
            # Store original threshold for reporting
            self.raw_threshold = threshold
        else:
            # For binary/categorical, threshold is used as-is
            super().__init__(name=name, threshold=threshold, metric_type=metric_type)
            self.raw_threshold = threshold
        
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
        
        # Render the template with all required variables
        prompt = template.render(
            evaluation_prompt=self.evaluation_prompt,
            evaluation_steps=self.evaluation_steps,
            reasoning=self.reasoning,
            evaluation_examples=self.evaluation_examples,
            input=input,
            context_text=context_text,
            expected_output=expected_output,
            output=output,
            min_score=self.min_score,
            max_score=self.max_score,
            score_type=self.score_type.value
        )
        
        return prompt

    @llm.call(provider="provider_placeholder", model="model_placeholder", response_model=ScoreResponse)
    def run_evaluation(self, prompt: str) -> str:
        """
        Run the evaluation using Mirascope LLM call with structured response model.
        This function will be decorated with the actual provider and model at runtime.
        """
        return prompt

    def _process_score(self, raw_score: Union[float, str, int]) -> float:
        """
        Process the raw score based on the score type.
        
        Args:
            raw_score: The raw score from the LLM
            
        Returns:
            float: Processed score
        """
        if self.score_type == ScoreType.NUMERIC:
            # For numeric scores, ensure it's a float and within range
            try:
                score = float(raw_score)
                return max(min(score, self.max_score), self.min_score)
            except (ValueError, TypeError):
                return self.min_score
                
        elif self.score_type == ScoreType.BINARY:
            # For binary scores, convert to 1.0 or 0.0
            if isinstance(raw_score, str):
                raw_score = raw_score.lower().strip()
                if raw_score in ['true', 'yes', '1', 'pass', 'success', 'correct']:
                    return 1.0
                else:
                    return 0.0
            elif isinstance(raw_score, (int, float)):
                return 1.0 if raw_score > 0 else 0.0
            else:
                return 0.0
                
        elif self.score_type == ScoreType.CATEGORICAL:
            # For categorical scores, return as-is (could be string or number)
            if isinstance(raw_score, str):
                return raw_score
            else:
                return float(raw_score)
                
        return float(raw_score)

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
            
            # For numeric scores, normalize the score
            if self.score_type == ScoreType.NUMERIC:
                normalized_score = (processed_score - self.min_score) / (self.max_score - self.min_score)
                evaluation_score = normalized_score
            else:
                # For binary/categorical, use the processed score directly
                evaluation_score = processed_score
            
            # Check if the evaluation meets the threshold using the base class method
            is_successful = self.evaluate_score(
                score=evaluation_score,
                score_type=self.score_type,
                threshold=self.threshold,
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
                "threshold": self.threshold,
                "threshold_operator": self.threshold_operator.value if self.threshold_operator else None,
                "raw_threshold": getattr(self, "raw_threshold", self.threshold)
            }
            
            # Add score range info for numeric scores
            if self.score_type == ScoreType.NUMERIC:
                details.update({
                    "normalized_score": evaluation_score,
                    "min_score": self.min_score,
                    "max_score": self.max_score,
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
                "threshold": self.threshold,
                "threshold_operator": self.threshold_operator.value if self.threshold_operator else None,
                "raw_threshold": getattr(self, "raw_threshold", self.threshold)
            }
            
            # Add score range info for numeric scores
            if self.score_type == ScoreType.NUMERIC:
                details.update({
                    "min_score": self.min_score,
                    "max_score": self.max_score,
                })
            
            # Return a default minimal score
            return MetricResult(score=0.0, details=details) 