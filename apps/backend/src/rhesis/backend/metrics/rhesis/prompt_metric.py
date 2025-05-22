from typing import Dict, List, Any, Optional

from mirascope import llm
from pydantic import BaseModel, Field

from rhesis.backend.metrics.base import MetricResult
from rhesis.backend.metrics.rhesis.metric_base import RhesisMetricBase


class ScoreResponse(BaseModel):
    """Model for structured score response from LLM evaluation."""
    score: float = Field(description="Evaluation score")
    reason: str = Field(description="Explanation for the score", default="")


class DetailedScoreResponse(BaseModel):
    """Model for a more detailed evaluation response with multiple metrics."""
    overall_score: float = Field(description="Overall evaluation score")
    relevance_score: float = Field(description="How relevant the response is to the query")
    accuracy_score: float = Field(description="How accurate the response is compared to expected output")
    coherence_score: float = Field(description="How well-structured and coherent the response is")
    reasoning: str = Field(description="Brief reasoning for the scores")


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
        min_score: float = 1.0,
        max_score: float = 5.0,
        threshold: float = 0.5,
        provider: str = "openai",
        model: str = "gpt-4o",
        metric_type="rag",
        **kwargs
    ):
        super().__init__(name=name, threshold=threshold, metric_type=metric_type)
        self.evaluation_prompt = evaluation_prompt
        self.evaluation_steps = evaluation_steps
        self.reasoning = reasoning
        self.min_score = min_score
        self.max_score = max_score
        self.provider = provider
        self.model = model
        self.additional_params = kwargs

    @property
    def requires_ground_truth(self) -> bool:
        """This metric typically requires ground truth."""
        return True

    def get_prompt_template(self, input: str, output: str, expected_output: str, context: List[str] = None) -> str:
        """
        Generate the prompt to be sent to the LLM.
        """
        context_text = "\n".join(context) if context else "No context provided."
        
        prompt = f"""
        You will be given the LLM response to a prompt.

        Your task is to rate the LLM response based on the following criteria.

        Please make sure you read and understand these instructions carefully.

        Evaluation Criteria:
        {self.evaluation_prompt}

        Evaluation Steps:
        {self.evaluation_steps}

        Reasoning Process:
        {self.reasoning}

        Input Query: 
        {input}

        Context Information:
        {context_text}

        Expected Response:
        {expected_output}

        LLM Response to Evaluate:
        {output}

        Evaluation Form:
        Please provide a numerical score between {self.min_score} and {self.max_score} and a brief explanation.
        Return ONLY a JSON object with a 'score' field containing your evaluation and a 'reason' field with your explanation.
        Example: {{"score": 4.5, "reason": "The response effectively addresses the query with accurate information."}}
        """
        
        return prompt

    @llm.call(provider="provider_placeholder", model="model_placeholder", response_model=ScoreResponse)
    def run_evaluation(self, prompt: str) -> str:
        """
        Run the evaluation using Mirascope LLM call with structured response model.
        This function will be decorated with the actual provider and model at runtime.
        """
        return prompt

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
        
        # Return the result with both raw and normalized scores
        details = {
            "raw_score": raw_score,
            "normalized_score": normalized_score,
            "min_score": self.min_score,
            "max_score": self.max_score,
            "llm_response": str(response._response.content),
            "prompt": prompt,
            "reason": reason,
            "is_successful": is_successful,
            "threshold": self.threshold
        }
        
        return MetricResult(score=normalized_score, details=details)


class RhesisDetailedPromptMetric(RhesisPromptMetric):
    """
    An extended version of RhesisPromptMetric that provides multiple scores
    for different aspects of the evaluation using a more detailed response model.
    """
    
    def get_prompt_template(self, input: str, output: str, expected_output: str, context: List[str] = None) -> str:
        """
        Generate a more detailed prompt template requesting multiple evaluation scores.
        """
        context_text = "\n".join(context) if context else "No context provided."
        
        prompt = f"""
        You will be given the LLM response to a prompt.

        Your task is to rate the LLM response on multiple dimensions based on the following criteria.

        Please make sure you read and understand these instructions carefully.

        Evaluation Criteria:
        {self.evaluation_prompt}

        Evaluation Steps:
        {self.evaluation_steps}

        Reasoning Process:
        {self.reasoning}

        Input Query: 
        {input}

        Context Information:
        {context_text}

        Expected Response:
        {expected_output}

        LLM Response to Evaluate:
        {output}

        Evaluation Form:
        Please evaluate the response on the following dimensions, with scores between {self.min_score} and {self.max_score}:
        1. Overall score - your overall assessment
        2. Relevance score - how relevant the response is to the query
        3. Accuracy score - how accurate the response is compared to the expected output
        4. Coherence score - how well-structured and coherent the response is
        
        Return a JSON object with these fields and a brief reasoning explaining your evaluation.
        Example:
        {{
            "overall_score": 4.2,
            "relevance_score": 4.5,
            "accuracy_score": 4.0,
            "coherence_score": 4.3,
            "reasoning": "The response effectively addresses the query with accurate information presented in a coherent structure."
        }}
        """
        
        return prompt

    @llm.call(provider="provider_placeholder", model="model_placeholder", response_model=DetailedScoreResponse)
    def run_evaluation(self, prompt: str) -> str:
        """
        Run the evaluation using Mirascope LLM call with detailed structured response model.
        This function will be decorated with the actual provider and model at runtime.
        """
        return prompt
    
    def evaluate(
        self, input: str, output: str, expected_output: Optional[str], context: List[str] = None
    ) -> MetricResult:
        """
        Evaluate the output using the LLM with the detailed prompt template.
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
        
        # Run the evaluation with structured response model
        response = evaluation_fn(prompt)
        
        # Get the overall score
        raw_score = response.overall_score
        
        # Ensure the score is within the min-max range
        raw_score = max(min(raw_score, self.max_score), self.min_score)
        
        # Normalize score to 0-1 range for consistent evaluation
        normalized_score = (raw_score - self.min_score) / (self.max_score - self.min_score)
        
        # Check if the evaluation meets the threshold
        is_successful = normalized_score >= self.threshold
        
        # Compile the reason from the reasoning field
        reason = response.reasoning
        
        # Return the result with both raw and normalized scores and all detailed scores
        details = {
            "raw_score": raw_score,
            "normalized_score": normalized_score,
            "relevance_score": response.relevance_score,
            "accuracy_score": response.accuracy_score,
            "coherence_score": response.coherence_score,
            "reasoning": response.reasoning,
            "min_score": self.min_score,
            "max_score": self.max_score,
            "llm_response": str(response._response.content),
            "prompt": prompt,
            "reason": reason,
            "is_successful": is_successful,
            "threshold": self.threshold
        }
        
        return MetricResult(score=normalized_score, details=details) 