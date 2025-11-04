"""
Context Retention metric for evaluating correct usage of provided context.
"""

from typing import Optional, Union

from rhesis.sdk.metrics import NumericJudge
from rhesis.sdk.models import BaseLLM


class ContextRetentionJudge(NumericJudge):
    """
    Evaluates whether the model correctly used the provided context.

    This metric assesses how well the output incorporates and respects
    information from the provided context (system prompt or additional context).

    Inherits from NumericJudge with prepopulated evaluation criteria.
    """

    def __init__(
        self,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        threshold: Optional[float] = None,
        model: Optional[Union[str, BaseLLM]] = None,
        **kwargs,
    ):
        """
        Initialize the ContextRetentionJudge metric.

        Args:
            min_score: Minimum possible score (defaults to 0)
            max_score: Maximum possible score (defaults to 1)
            threshold: Success threshold (defaults to midpoint)
            model: The LLM model to use for evaluation
            **kwargs: Additional keyword arguments passed to NumericJudge
        """
        evaluation_prompt = """You are evaluating CONTEXT RETENTION - how well the model incorporated and respected the provided context.

Context retention measures whether the model actually USED the context information when generating its response.

WHAT TO EVALUATE:

1. CONTEXT INCORPORATION:
   - Did the model use information from the provided context?
   - Are facts/details from the context reflected in the response?
   - Did the model reference or build upon the context?

2. CONTEXT RESPECT:
   - Did the model contradict information in the context?
   - Did the model ignore relevant context entirely?
   - Did the model make up information not in the context when it should use context?

3. APPROPRIATE USAGE:
   - Is the context information used accurately?
   - Is the usage relevant to answering the input query?
   - Did the model balance context with general knowledge appropriately?

IMPORTANT GUIDELINES:
- HIGH scores: Model clearly used and respected context
- MID scores: Model partially used context or mixed with outside info
- LOW scores: Model ignored context, contradicted it, or made up info
- If no context was needed for the query, but model used it anyway: HIGH score
- If context was essential but ignored: LOW score

EXAMPLES:

Example 1:
Context: "The capital of France is Paris"
Query: "What is the capital of France?"
Response: "The capital is Paris"
SCORE: HIGH (correctly used context)

Example 2:
Context: "The capital of France is Paris"
Query: "What is the capital of France?"
Response: "The capital is London"
SCORE: LOW (contradicted context)

Example 3:
Context: "The meeting is at 3pm"
Query: "When is the meeting?"
Response: "Let me help you schedule meetings..."
SCORE: LOW (ignored context, deflected)

Example 4:
Context: "The user's name is Alice"
Query: "What is 2+2?"
Response: "Hello Alice! 2+2 equals 4"
SCORE: HIGH (used context appropriately even though not essential)

SCORING GUIDE:
- 0.0-0.3: Ignored or contradicted context, made up information
- 0.4-0.6: Partially used context, some contradictions or omissions
- 0.7-0.9: Mostly used context correctly, minor issues
- 1.0: Perfectly incorporated and respected all relevant context"""

        evaluation_steps = """1. Read the provided context carefully
2. Read the input query - what information from context is relevant?
3. Read the LLM response
4. Check: Did the model use relevant context information?
5. Check: Did the model contradict or ignore the context?
6. Check: Did the model make up info when context was available?
7. Assign score based on context usage quality
8. Explain with specific examples of good/bad context usage"""

        super().__init__(
            name="context_retention",
            evaluation_prompt=evaluation_prompt,
            evaluation_steps=evaluation_steps,
            min_score=min_score,
            max_score=max_score,
            threshold=threshold,
            model=model,
            requires_context=True,
            **kwargs,
        )
