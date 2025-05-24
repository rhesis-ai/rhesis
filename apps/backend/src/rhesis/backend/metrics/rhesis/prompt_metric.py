from typing import Dict, List, Any, Optional
import os
from jinja2 import Environment, FileSystemLoader, select_autoescape

from mirascope import llm
from pydantic import BaseModel, Field

from rhesis.backend.metrics.base import MetricResult, retry_evaluation
from rhesis.backend.metrics.rhesis.metric_base import RhesisMetricBase


class ScoreResponse(BaseModel):
    """Model for structured score response from LLM evaluation."""
    score: float = Field(description="Evaluation score")
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
        min_score: float = 1.0,
        max_score: float = 5.0,
        threshold: float = 0.5,
        provider: str = "openai",
        model: str = "gpt-4o",
        metric_type="rag",
        **kwargs
    ):
        # Store the score range
        self.min_score = min_score
        self.max_score = max_score
        
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
        
        # Store other parameters
        self.evaluation_prompt = evaluation_prompt
        self.evaluation_steps = evaluation_steps
        self.reasoning = reasoning
        self.evaluation_examples = evaluation_examples
        self.provider = provider
        self.model = model
        self.additional_params = kwargs
        
        # Store original threshold for reporting
        self.raw_threshold = threshold
        
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
            max_score=self.max_score
        )
        
        return prompt

    @llm.call(provider="provider_placeholder", model="model_placeholder", response_model=ScoreResponse)
    def run_evaluation(self, prompt: str) -> str:
        """
        Run the evaluation using Mirascope LLM call with structured response model.
        This function will be decorated with the actual provider and model at runtime.
        """
        return prompt

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
            
            # Get the score directly from the structured response
            raw_score = response.score
            reason = response.reason if hasattr(response, 'reason') and response.reason else f"Score: {raw_score}"
            
            # Ensure the score is within the min-max range
            raw_score = max(min(raw_score, self.max_score), self.min_score)
            
            # Normalize score to 0-1 range for consistent evaluation
            normalized_score = (raw_score - self.min_score) / (self.max_score - self.min_score)
            
            # Check if the evaluation meets the threshold
            is_successful = normalized_score >= self.threshold
            
            # Get the original LLM response content for debugging
            llm_response_content = str(response._response.content) if hasattr(response, '_response') else "No raw response available"
            
            # Return the result with both raw and normalized scores
            details = {
                "raw_score": raw_score,
                "normalized_score": normalized_score,
                "min_score": self.min_score,
                "max_score": self.max_score,
                "llm_response": llm_response_content,
                "prompt": prompt,
                "reason": reason,
                "is_successful": is_successful,
                "threshold": self.threshold,
                "raw_threshold": getattr(self, "raw_threshold", self.threshold)
            }
            
            return MetricResult(score=normalized_score, details=details)
            
        except Exception as e:
            # Log the error for debugging
            error_msg = f"Error evaluating with {self.name}: {str(e)}"
            # Return a fallback score with error information
            details = {
                "error": error_msg,
                "prompt": prompt,
                "min_score": self.min_score,
                "max_score": self.max_score,
                "threshold": self.threshold,
                "raw_threshold": getattr(self, "raw_threshold", self.threshold)
            }
            # Return a default minimal score
            return MetricResult(score=0.0, details=details) 