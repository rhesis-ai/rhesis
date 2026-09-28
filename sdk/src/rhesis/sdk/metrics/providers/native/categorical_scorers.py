"""How a categorical judge gets a category out of its model, one scorer per model kind.

A text LLM is prompted and asked for ``{score, reason}`` JSON. A decision model
(Jev) is asked one ``choice`` question over the categories. Supporting another
model kind means adding a scorer here and listing it in ``_SCORERS``.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional

from pydantic import create_model

from rhesis.sdk.metrics.constants import JUDGE_TEMPERATURE
from rhesis.sdk.models.base import BaseDecisionModel, BaseLLM

if TYPE_CHECKING:
    from rhesis.sdk.metrics.providers.native.categorical_judge import CategoricalJudge


@dataclass(frozen=True)
class Evidence:
    """What the judge was handed to evaluate."""

    input: str
    output: str
    expected_output: str
    context: List[str]
    metadata_text: Optional[str] = None
    tool_calls_text: Optional[str] = None


@dataclass(frozen=True)
class Request:
    """A prepared request: ``prompt`` is recorded in the result, ``payload`` is sent."""

    prompt: str
    payload: Any


@dataclass(frozen=True)
class Verdict:
    score: str
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)


class CategoricalScorer(ABC):
    def __init__(self, judge: "CategoricalJudge"):
        self.judge = judge

    @abstractmethod
    def prepare(self, evidence: Evidence) -> Request:
        """Build the request. Raises ValueError when the evidence can't be rendered."""

    @abstractmethod
    async def a_score(self, request: Request) -> Verdict:
        """Send the request and read the chosen category back."""


class TextCategoricalScorer(CategoricalScorer):
    def prepare(self, evidence: Evidence) -> Request:
        prompt = self.judge._get_prompt_template(
            evidence.input,
            evidence.output,
            evidence.expected_output,
            evidence.context,
            metadata_text=evidence.metadata_text,
            tool_calls_text=evidence.tool_calls_text,
        )
        return Request(prompt=prompt, payload=prompt)

    async def a_score(self, request: Request) -> Verdict:
        categories = self.judge.categories
        score_literal = (
            Literal[tuple(categories)] if len(categories) > 1 else Literal[categories[0]]
        )
        schema = create_model(
            "ScoreResponseCategorical", score=(score_literal, ...), reason=(str, ...)
        )
        response = await self.judge.model.a_generate(
            request.payload, schema=schema, temperature=JUDGE_TEMPERATURE
        )
        parsed = schema(**response)  # type: ignore[arg-type]
        return Verdict(score=parsed.score, reason=parsed.reason)  # type: ignore[attr-defined]


class DecisionCategoricalScorer(CategoricalScorer):
    """The evidence goes in as ``state`` and the metric's criteria as the question."""

    QUESTION_ID = "score"

    def prepare(self, evidence: Evidence) -> Request:
        state = {
            "input": evidence.input,
            "context": "\n".join(evidence.context) if evidence.context else None,
            "metadata": evidence.metadata_text,
            "tool_calls": evidence.tool_calls_text,
            "expected_output": evidence.expected_output,
            "output_to_evaluate": evidence.output,
        }
        state = {k: v for k, v in state.items() if v}
        judge = self.judge
        instructions = "\n\n".join(
            part
            for part in (
                judge.evaluation_prompt,
                judge.evaluation_steps,
                judge.reasoning,
                judge.evaluation_examples,
            )
            if part
        )
        # Categories have no descriptions of their own, so the name stands in for one.
        question = {
            "type": "choice",
            "instructions": instructions,
            "criteria": {category: category for category in judge.categories},
        }
        prompt = json.dumps({"state": state, "question": question}, indent=2)
        return Request(prompt=prompt, payload=(state, {self.QUESTION_ID: question}))

    async def a_score(self, request: Request) -> Verdict:
        state, questions = request.payload
        answers = await self.judge.model.a_decide(state, questions)
        answer = answers[self.QUESTION_ID]
        score = answer["choice"]
        probabilities = answer.get("probabilities") or {}
        probability = probabilities.get(score)
        # Decision models give no reasoning; the probability is the explanation there is.
        reason = f"Chose '{score}'" + (
            f" (p={probability:.2f})." if probability is not None else "."
        )
        return Verdict(
            score=score,
            reason=reason,
            details={"probabilities": probabilities, "confidence": answer.get("confidence")},
        )


_SCORERS = (
    (BaseDecisionModel, DecisionCategoricalScorer),
    (BaseLLM, TextCategoricalScorer),
)


def scorer_for(judge: "CategoricalJudge") -> CategoricalScorer:
    for model_type, scorer in _SCORERS:
        if isinstance(judge.model, model_type):
            return scorer(judge)
    raise TypeError(f"No categorical scorer for {type(judge.model).__name__}")
