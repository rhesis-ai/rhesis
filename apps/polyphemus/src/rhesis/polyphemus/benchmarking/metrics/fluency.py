"""
Fluency metric for evaluating grammar, coherence, and naturalness of LLM outputs.
"""

from typing import Optional, Union

from rhesis.sdk.metrics import NumericJudge
from rhesis.sdk.models import BaseLLM


class FluencyJudge(NumericJudge):
    """
    Evaluates the fluency of text based on grammar, coherence, and naturalness.

    This metric assesses how well-written and natural the output text is,
    considering grammatical correctness, logical flow, and overall readability.

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
        Initialize the FluencyJudge metric.

        Args:
            min_score: Minimum possible score (defaults to 0)
            max_score: Maximum possible score (defaults to 1)
            threshold: Success threshold (defaults to midpoint)
            model: The LLM model to use for evaluation
            **kwargs: Additional keyword arguments passed to NumericJudge
        """
        evaluation_prompt = """You are evaluating the FLUENCY of text - how well-written, grammatical, and natural it is.

Fluency measures the linguistic quality of the output, NOT its content accuracy or helpfulness.

WHAT TO EVALUATE:

1. GRAMMAR & SYNTAX:
   - Are sentences grammatically correct?
   - Is punctuation used properly?
   - Are there spelling errors?
   - Is capitalization appropriate?

2. COHERENCE & FLOW:
   - Do sentences connect logically?
   - Are transitions smooth?
   - Is the structure clear and organized?
   - Does it read naturally?

3. NATURALNESS:
   - Does it sound like natural human language?
   - Is the writing style appropriate?
   - Are word choices appropriate?
   - Is phrasing awkward or stilted?

IMPORTANT GUIDELINES:
- Focus ONLY on linguistic quality, NOT content
- Grammatically perfect gibberish scores LOW (lacks coherence)
- Coherent but ungrammatical text scores MID (has structure issues)
- Natural, well-written text scores HIGH (even if content is wrong)
- Ignore whether the response is helpful/accurate - that's not fluency

SCORING GUIDE:
- 0.0-0.3: Severe grammar errors, incoherent, unnatural
- 0.4-0.6: Some errors, mostly coherent, somewhat natural
- 0.7-0.9: Minor errors, coherent, natural
- 1.0: Perfect grammar, highly coherent, completely natural"""

        evaluation_steps = """1. Read the LLM response carefully
2. Check for grammatical errors (spelling, punctuation, syntax)
3. Assess coherence (logical flow, organization, connections)
4. Evaluate naturalness (sounds human, appropriate phrasing)
5. Assign score based ONLY on linguistic quality
6. Explain your score citing specific fluency issues or strengths"""

        super().__init__(
            name="fluency",
            evaluation_prompt=evaluation_prompt,
            evaluation_steps=evaluation_steps,
            min_score=min_score,
            max_score=max_score,
            threshold=threshold,
            model=model,
            **kwargs,
        )
