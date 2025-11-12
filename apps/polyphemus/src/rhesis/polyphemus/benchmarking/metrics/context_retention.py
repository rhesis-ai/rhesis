"""
Context Retention metric for evaluating correct usage of provided context.
Matches SDK patterns by accepting context as List[str].
"""

from typing import List, Optional, Union

from rhesis.sdk.metrics import MetricResult, NumericJudge
from rhesis.sdk.models import BaseLLM


class ContextRetentionJudge(NumericJudge):
    """
    Evaluates whether the model correctly used the provided context.

    This metric assesses how well the output incorporates and respects
    information from the provided context chunks (RAG-style evaluation).

    Matches SDK patterns:
    - Accepts context as List[str] (list of context chunks)
    - Joins chunks with newlines for evaluation prompt
    - Uses NumericJudge base class with comprehensive evaluation criteria

    Score interpretation:
    - 1.0: Perfect context usage - all relevant info incorporated, no contradictions
    - 0.7-0.9: Strong usage - most context used correctly, minor omissions
    - 0.4-0.6: Partial usage - some context used but significant gaps/issues
    - 0.0-0.3: Poor usage - context ignored, contradicted, or fabricated info
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
            threshold: Success threshold (defaults to 0.7)
            model: The LLM model to use for evaluation
            **kwargs: Additional keyword arguments passed to NumericJudge
        """
        evaluation_prompt = """You are evaluating CONTEXT UTILIZATION AND FIDELITY.

Your task is to assess how well the model used the provided context chunks when generating its response.

EVALUATION CRITERIA:

1. INFORMATION EXTRACTION (40%)
   - Did the model identify and extract relevant information from the context?
   - Were key facts, details, or data points from the context incorporated?
   - Did the model prioritize the most relevant context chunks?

2. FACTUAL ACCURACY (30%)
   - Is the response factually consistent with the provided context?
   - Are there any contradictions between the response and context?
   - Did the model avoid fabricating information when context was available?

3. CONTEXT DEPENDENCY (20%)
   - When context is essential to answer the query, did the model rely on it?
   - Did the model appropriately ground its response in the provided context?
   - Was the context used as the primary information source when needed?

4. SYNTHESIS & APPLICATION (10%)
   - Did the model synthesize information across multiple context chunks?
   - Was the context applied appropriately to answer the specific query?
   - Did the model balance context with reasonable inference when appropriate?

SCORING GUIDELINES:

SCORE 0.9-1.0 (Excellent):
- All relevant context information is accurately incorporated
- No contradictions or fabricated information
- Context is the clear foundation of the response
- Multi-chunk synthesis is performed when needed
- Response directly addresses query using context

SCORE 0.7-0.8 (Good):
- Most relevant context is used correctly
- Minor omissions of non-critical context details
- No significant contradictions
- Generally well-grounded in provided context

SCORE 0.5-0.6 (Fair):
- Some context is used but with significant gaps
- May include some information not from context when it should
- Partial contradictions or misinterpretations
- Context usage is inconsistent

SCORE 0.3-0.4 (Poor):
- Minimal context usage despite clear relevance
- Multiple contradictions with provided context
- Significant fabrication when context was available
- Context mostly ignored

SCORE 0.0-0.2 (Very Poor):
- Context completely ignored despite being essential
- Response contradicts context on core facts
- Entirely fabricated response when context provided answer
- No evidence of context consideration

SPECIAL CASES:
- If query doesn't require context but model still uses it appropriately: HIGH score
- If context is ambiguous but model handles it reasonably: MODERATE-HIGH score
- If context lacks needed info and model acknowledges this: MODERATE score
- If context lacks info but model fabricates anyway: LOW score"""

        evaluation_steps = """Follow these steps systematically:

1. ANALYZE THE CONTEXT
   - Read all provided context chunks carefully
   - Identify key facts, entities, dates, and relationships
   - Note any ambiguities or gaps in the context

2. ANALYZE THE QUERY
   - What information is the query requesting?
   - Which context chunks are relevant to the query?
   - Is context essential or supplementary for this query?

3. ANALYZE THE RESPONSE
   - What claims or statements does the response make?
   - Which statements come from context vs. general knowledge?
   - Are there any statements that contradict the context?

4. EVALUATE INFORMATION EXTRACTION
   - List relevant context facts that WERE incorporated
   - List relevant context facts that WERE NOT incorporated
   - Assess completeness of extraction (40% weight)

5. EVALUATE FACTUAL ACCURACY
   - Check each claim against the context
   - Identify any contradictions or inaccuracies
   - Note any fabricated details when context was available
   - Assess accuracy (30% weight)

6. EVALUATE CONTEXT DEPENDENCY
   - Was context used as primary source when it should be?
   - Did model inappropriately rely on outside knowledge?
   - Assess grounding in context (20% weight)

7. EVALUATE SYNTHESIS
   - Was information combined across chunks effectively?
   - Was context applied appropriately to the query?
   - Assess synthesis quality (10% weight)

8. COMPUTE FINAL SCORE
   - Weight each criterion by its percentage
   - Consider overall context utilization quality
   - Assign final score on 0-1 scale

9. WRITE EXPLANATION
   - Provide specific examples of good/poor context usage
   - Quote relevant parts of context and response
   - Justify the score with concrete evidence"""

        evaluation_examples = """Example 1 - Excellent Usage (Score: 0.95):
Context chunks:
- "Q3 2024 revenue was $45.2M, up 23% YoY"
- "Customer count increased to 1,250 from 980 in Q2"
- "Average deal size was $36K"

Query: "How did the company perform in Q3 2024?"
Response: "In Q3 2024, the company had strong performance with revenue reaching $45.2M (23% year-over-year growth). The customer base expanded to 1,250 customers from 980 in Q2, with an average deal size of $36K."

Analysis: Perfect extraction and synthesis of all three context chunks. Factually accurate. Well-structured response directly addressing the query.

---

Example 2 - Good Usage (Score: 0.75):
Context chunks:
- "The product launch is scheduled for March 15th"
- "Marketing budget is $500K"
- "Target audience is enterprise customers"

Query: "When is the product launching?"
Response: "The product launch is scheduled for March 15th. The company is targeting enterprise customers."

Analysis: Correctly extracted launch date and target audience. Missed marketing budget (less critical for this query). No contradictions. Solid usage.

---

Example 3 - Fair Usage (Score: 0.55):
Context chunks:
- "CEO Jane Smith joined in 2020"
- "Company founded in 2018"
- "Headquarters in Austin, Texas"

Query: "Tell me about the company's leadership."
Response: "The company has experienced leadership and is based in Austin. They've been growing steadily since founding."

Analysis: Vague reference to leadership without mentioning CEO name or tenure. Mentioned HQ but missed founding year. Generic statement about growth not grounded in provided context.

---

Example 4 - Poor Usage (Score: 0.25):
Context chunks:
- "The bug affects only Windows 10 users"
- "Workaround: disable auto-update temporarily"
- "Fix will be released in version 2.1.5"

Query: "How do I fix this bug?"
Response: "You should reinstall the software and make sure you're on the latest version. Contact support if issues persist."

Analysis: Completely ignored the provided workaround and fix version. Suggested generic troubleshooting not mentioned in context. Failed to specify Windows 10 specificity.

---

Example 5 - Very Poor Usage (Score: 0.10):
Context chunks:
- "Our office hours are Monday-Friday, 9 AM - 5 PM EST"
- "Weekend support available for enterprise tier only"
- "Response time: 24-48 hours for standard tickets"

Query: "When can I reach support?"
Response: "Our support team is available 24/7 to assist you with any questions. You can expect immediate responses through our live chat."

Analysis: Directly contradicts context (not 24/7, not immediate response). Fabricated live chat feature. Ignored actual office hours and response times."""

        super().__init__(
            name="context_retention",
            evaluation_prompt=evaluation_prompt,
            evaluation_steps=evaluation_steps,
            evaluation_examples=evaluation_examples,
            min_score=min_score if min_score is not None else 0.0,
            max_score=max_score if max_score is not None else 1.0,
            threshold=threshold if threshold is not None else 0.7,
            model=model,
            requires_context=True,
            **kwargs,
        )

    def evaluate(
        self,
        input: str,
        output: str,
        expected_output: Optional[str] = None,
        context: Optional[List[str]] = None,
        **kwargs,
    ) -> MetricResult:
        """
        Evaluate context retention with SDK-compatible interface.

        Args:
            input: The input query/prompt
            output: The model's response to evaluate
            expected_output: Optional expected response
            context: List of context chunks (SDK format)
            **kwargs: Additional arguments

        Returns:
            MetricResult with score (0-1) and explanation
        """
        # Convert context list to format expected by parent class
        # The SDK's NumericJudge expects context as List[str] and handles joining internally
        return super().evaluate(
            input=input,
            output=output,
            expected_output=expected_output,
            context=context,
            **kwargs,
        )
