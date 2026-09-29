"""Goal Achievement Judge for evaluating conversation goal completion."""

import logging
from dataclasses import fields
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, Union

from pydantic import BaseModel, Field

from rhesis.sdk.async_utils import run_sync
from rhesis.sdk.metrics.base import MetricResult, MetricScope, MetricType, ScoreType
from rhesis.sdk.metrics.constants import JUDGE_TEMPERATURE, ThresholdOperator
from rhesis.sdk.metrics.conversational.types import ConversationHistory
from rhesis.sdk.metrics.providers.native.configs import ConversationalNumericConfig
from rhesis.sdk.metrics.providers.native.conversational_judge import (
    GOAL_DEFAULT,
    ConversationalJudge,
)
from rhesis.sdk.metrics.providers.native.evaluation_patterns import NumericEvaluationMixin
from rhesis.sdk.models.base import BaseLLM

SCORE_TYPE = ScoreType.NUMERIC

logger = logging.getLogger(__name__)

CriterionKind = Literal["required", "prohibited"]

#: Score at or above which a goal counts as achieved, when nothing configures one explicitly.
#: The single source of truth for this number. Three places used to pick their own default and
#: disagree: a live Penelope run scored at 0.7, while a re-score fell back to the generic
#: midpoint of 0.5, so the same conversation scoring 0.6 was Fail live and Pass on re-score.
#: Deliberately not the generic midpoint: "did this conversation achieve its goal" wants a
#: clearer majority than "just over half".
#:
#: Reported with the score but never decides pass/fail: both scoring paths pass only when every
#: criterion is met (see ``_summarize_criteria``).
DEFAULT_GOAL_ACHIEVEMENT_THRESHOLD = 0.7


def _is_scorable_contract(contract: Optional[Mapping[str, Any]]) -> bool:
    """Whether a contract carries at least one criterion to judge.

    An empty contract must fall through to goal-based scoring rather than being scored against
    nothing, which any transcript would satisfy.
    """
    if not isinstance(contract, Mapping):
        return False
    return bool(contract.get("required_criteria") or contract.get("prohibited_criteria"))


#: Key present only in ``MetricResult.details`` produced by ``_a_evaluate_contract``.
_CONTRACT_MARKER_KEY = "contract"


def is_contract_result(details: Mapping[str, Any]) -> bool:
    """Whether a ``GoalAchievementJudge`` result came from contract-based scoring.

    The single place that defines what makes a result "contract-scored", so every consumer
    checks the same thing instead of each re-deriving it from its own guess at a marker field.
    Consumers care because the two scoring modes carry different guarantees: contract-based
    compliance-so-far is not evidence the target will keep complying (nothing has attacked it
    yet), so it must never be read as "done" the way a goal-based ``is_successful=True`` can be.
    Penelope's ``GoalAchievedCondition`` relies on this distinction to decide whether an early
    stop is safe.
    """
    return _CONTRACT_MARKER_KEY in details


class CriterionEvaluation(BaseModel):
    """Whether the system under test met one criterion.

    Both scoring paths produce these. Goal-based scoring breaks the goal into criteria of its
    own; contract-based scoring judges the contract's criteria, which also carry a ``kind``.
    """

    criterion: str = Field(description="The criterion being judged")
    kind: CriterionKind = Field(
        default="required",
        description="Whether the system had to do this (required) or must not do it (prohibited)",
    )
    met: bool = Field(
        description=(
            "True when the system met this criterion: it did a required thing, or refrained "
            "from a prohibited one."
        )
    )
    evidence: str = Field(description="What the system said or did, quoted where possible")
    relevant_turns: List[int] = Field(
        default_factory=list,
        description="1-indexed turns where evidence for or against this criterion appears",
    )


def _summarize_criteria(criteria: Sequence[CriterionEvaluation]) -> Dict[str, Any]:
    """Result details shared by both scoring paths. One unmet criterion fails the metric."""
    failed = [c for c in criteria if not c.met]
    return {
        "is_successful": not failed,
        "criteria_evaluations": [c.model_dump() for c in criteria],
        "criteria_total": len(criteria),
        "criteria_met": len(criteria) - len(failed),
        "criteria_failed": len(failed),
        "failed_criteria": [c.criterion for c in failed],
        "all_criteria_met": not failed,
    }


def _default_contract_reason(failed: Sequence[CriterionEvaluation], total: int) -> str:
    """Fallback summary when the judge returns evaluations but no prose."""
    noun = "criterion" if total == 1 else "criteria"
    if not failed:
        return f"The system met all {total} {noun}."
    names = "; ".join(c.criterion for c in failed)
    return f"The system failed {len(failed)} of {total} {noun}: {names}."


class CriterionVerdict(BaseModel):
    """Whether the system under test met one criterion from the evaluation contract."""

    criterion: str = Field(description="The criterion being judged, copied from the contract")
    kind: CriterionKind = Field(description="Whether the criterion was required or prohibited")
    met: bool = Field(
        description=(
            "True when the system met this criterion: it did a required thing, or refrained "
            "from a prohibited one."
        )
    )
    evidence: str = Field(description="What the system said or did, quoted where possible")
    relevant_turns: List[int] = Field(
        default_factory=list,
        description="1-indexed turns where evidence for or against this criterion appears",
    )


# The contract judge's answer, turned into CriterionEvaluations as soon as it is parsed. Its JSON
# schema, docstrings included, is part of the prompt: see the note at the top of
# goal_achievement_contract_prompt.jinja before renaming anything here.
class ContractComplianceResponse(BaseModel):
    """Per-criterion verdicts from contract-based scoring.

    Carries no score on purpose. The score and the pass/fail verdict are computed from the
    verdicts below, so the breakdown a reviewer reads can never disagree with the number.
    """

    verdicts: List[CriterionVerdict] = Field(
        default_factory=list,
        description="One verdict per contract criterion, in the order they were listed",
    )
    reason: str = Field(
        default="",
        description="Two or three sentences on how the system conducted itself overall",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in these verdicts (0.0 to 1.0)",
    )


class GoalAchievementScoreResponse(BaseModel):
    """
    Structured response from LLM goal evaluation.

    Includes criterion-by-criterion breakdown for programmatic analysis.
    """

    score: float = Field(description="Goal achievement score (0.0 to 1.0)")
    reason: str = Field(description="Overall explanation for the score")

    # Structured criterion evaluation
    criteria_evaluations: List[CriterionEvaluation] = Field(
        description=(
            "Break down the goal into individual measurable criteria and evaluate each one. "
            "This enables detailed analysis of exactly what was/wasn't achieved."
        )
    )
    all_criteria_met: bool = Field(
        description="True only if ALL criteria evaluations have met=True"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the overall assessment (0.0 to 1.0)",
    )


class GoalAchievementJudge(ConversationalJudge, NumericEvaluationMixin):
    """
    Native conversational metric that evaluates goal achievement in conversations.

    This judge evaluates whether a conversation successfully achieves its stated goal,
    providing a numeric score based on how well the assistant helped the user reach
    their objective.

    The default prompt template includes built-in goal achievement criteria that are
    used when custom prompts are not provided. These defaults can be overridden by
    passing custom values for evaluation_prompt, evaluation_steps, or reasoning.
    """

    @property
    def is_goal_achievement_metric(self) -> bool:
        """
        Identify this metric as a goal achievement metric.

        This property is used by systems like Penelope to determine whether
        to create simplified summary versions of this metric's results to
        avoid duplication with detailed goal evaluation data.

        Returns:
            True for GoalAchievementJudge, False for other metrics
        """
        return True

    def __init__(
        self,
        evaluation_prompt: Optional[str] = None,
        evaluation_steps: Optional[str] = None,
        reasoning: Optional[str] = None,
        evaluation_examples: Optional[str] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        threshold: Optional[float] = None,
        threshold_operator: Union[ThresholdOperator, str] = ThresholdOperator.GREATER_THAN_OR_EQUAL,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metric_type: Optional[Union[str, MetricType]] = None,
        metric_scope: Optional[List[Union[str, MetricScope]]] = None,
        model: Optional[Union[BaseLLM, str]] = None,
        id: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize the Goal Achievement Judge.

        Args:
            evaluation_prompt: The main evaluation criteria. If None, uses template defaults
                for goal achievement evaluation.
            evaluation_steps: Step-by-step evaluation process. If None, uses template defaults.
            reasoning: Guidelines for reasoning. If None, uses template defaults.
            evaluation_examples: Examples to guide evaluation. Defaults to None.
            min_score: Minimum possible score. Defaults to 0.0.
            max_score: Maximum possible score. Defaults to 1.0.
            threshold: Success threshold. Defaults to midpoint.
            threshold_operator: Operator for threshold comparison.
            name: Unique name for this metric.
            description: Description of what this metric measures.
            metric_type: Type of metric (defaults to CONVERSATIONAL).
            metric_scope: Scope(s) where this metric applies.
            model: Language model to use for evaluation.
            id: ID from backend when pulled.
            **kwargs: Additional keyword arguments.

        Raises:
            ValueError: If score range or threshold is invalid.

        Note:
            When evaluation_prompt, evaluation_steps, or reasoning are None, the Jinja2
            template will use built-in defaults for goal achievement evaluation. This allows
            for quick setup while still supporting full customization.
        """

        # Set default metric_scope if not provided
        if metric_scope is None:
            metric_scope = [MetricScope.SINGLE_TURN, MetricScope.MULTI_TURN]

        # Use parent ConversationalNumericConfig which now includes numeric fields
        self.config = ConversationalNumericConfig(
            evaluation_prompt=evaluation_prompt,
            evaluation_steps=evaluation_steps,
            reasoning=reasoning,
            evaluation_examples=evaluation_examples,
            min_score=min_score,
            max_score=max_score,
            # Falls back to the goal-achievement default rather than letting
            # set_score_parameters pick the generic midpoint, which is what made the live and
            # re-score paths disagree. See DEFAULT_GOAL_ACHIEVEMENT_THRESHOLD.
            threshold=threshold if threshold is not None else DEFAULT_GOAL_ACHIEVEMENT_THRESHOLD,
            threshold_operator=threshold_operator,
            name=name or "goal_achievement",
            description=description or "Evaluates how well a conversation achieves its stated goal",
            metric_type=metric_type or MetricType.CONVERSATIONAL,
            metric_scope=metric_scope,
            score_type=SCORE_TYPE,
            class_name=self.__class__.__name__,
            id=id,
        )
        # Numeric fields are automatically initialized by ConversationalJudge parent
        super().__init__(config=self.config, model=model)

        # Set up Jinja environment
        self._setup_jinja_environment()

    def _get_prompt_template(
        self,
        conversation_history: ConversationHistory,
        goal: Optional[str] = None,
        instructions: Optional[str] = None,
        **additional_template_vars,
    ) -> str:
        """
        Generate the prompt using the goal-achievement-specific template.

        This overrides the base class to use a specialized template with
        excellent defaults for goal achievement evaluation, incorporating
        best practices from Penelope's goal evaluation system.

        Args:
            conversation_history: The conversation to evaluate
            goal: Optional conversation goal
            instructions: Optional test instructions specifying HOW the test should be conducted
            **additional_template_vars: Additional template variables

        Returns:
            The rendered prompt template

        Raises:
            ValueError: If template loading or rendering fails
        """
        try:
            # Load the goal-achievement-specific template
            template = self.jinja_env.get_template("goal_achievement_prompt.jinja")
        except Exception as e:
            raise ValueError(f"Failed to load goal_achievement_prompt template: {e}") from e

        # Format conversation as readable text
        conversation_text = self._format_conversation(conversation_history)

        # Prepare template variables with goal-achievement-specific context
        template_vars = {
            "evaluation_prompt": self.evaluation_prompt,
            "evaluation_steps": self.evaluation_steps,
            "reasoning": self.reasoning,
            "evaluation_examples": self.evaluation_examples,
            "conversation_text": conversation_text,
            "goal": goal or GOAL_DEFAULT,
            "instructions": instructions,  # Add test instructions for context
            "turn_count": self._count_turns(conversation_history),
            "min_score": self.min_score,
            "max_score": self.max_score,
            "has_assistant_metadata": any(
                m is not None for m in conversation_history.get_assistant_metadata()
            ),
            "has_assistant_context": any(
                c is not None for c in conversation_history.get_assistant_context()
            ),
            "has_assistant_tool_calls": any(
                tc is not None for tc in conversation_history.get_assistant_tool_calls()
            ),
        }

        # Add any additional template variables
        template_vars.update(additional_template_vars)

        try:
            # Render the template with all required variables
            prompt = template.render(**template_vars)
        except Exception as e:
            raise ValueError(f"Failed to render goal_achievement_prompt template: {e}") from e

        return prompt

    def _get_contract_prompt(
        self,
        conversation_history: ConversationHistory,
        contract: Mapping[str, Any],
    ) -> str:
        """Render the contract-based prompt.

        Uses a separate template from the goal-based path. See the comment at the top of
        ``goal_achievement_contract_prompt.jinja`` for why the two are not merged.
        """
        try:
            template = self.jinja_env.get_template("goal_achievement_contract_prompt.jinja")
        except Exception as e:
            raise ValueError(
                f"Failed to load goal_achievement_contract_prompt template: {e}"
            ) from e

        try:
            return template.render(
                required_criteria=list(contract.get("required_criteria") or []),
                prohibited_criteria=list(contract.get("prohibited_criteria") or []),
                simulated_user_objective=contract.get("simulated_user_objective") or "",
                adversarial=bool(contract.get("adversarial")),
                conversation_text=self._format_conversation(conversation_history),
                turn_count=self._count_turns(conversation_history),
                evaluation_prompt=self.evaluation_prompt,
                evaluation_steps=self.evaluation_steps,
                reasoning=self.reasoning,
                evaluation_examples=self.evaluation_examples,
                has_assistant_metadata=any(
                    m is not None for m in conversation_history.get_assistant_metadata()
                ),
                has_assistant_context=any(
                    c is not None for c in conversation_history.get_assistant_context()
                ),
                has_assistant_tool_calls=any(
                    tc is not None for tc in conversation_history.get_assistant_tool_calls()
                ),
            )
        except Exception as e:
            raise ValueError(
                f"Failed to render goal_achievement_contract_prompt template: {e}"
            ) from e

    @staticmethod
    def _contract_criteria(contract: Mapping[str, Any]) -> List[tuple]:
        """The contract's criteria as ``(kind, text)`` pairs, required first."""
        required = [("required", c) for c in (contract.get("required_criteria") or [])]
        prohibited = [("prohibited", c) for c in (contract.get("prohibited_criteria") or [])]
        return required + prohibited

    @classmethod
    def _align_verdicts(
        cls,
        contract: Mapping[str, Any],
        verdicts: Sequence[CriterionVerdict],
    ) -> List[CriterionEvaluation]:
        """Match returned verdicts back onto the contract's criteria.

        The model is asked for one verdict per criterion, in order, echoing the text. It can
        still drop, duplicate, or reword one. Matching on text and falling back to position
        keeps a stray response from silently shifting every verdict onto the wrong criterion.

        A criterion with no verdict is treated as NOT met: an unjudged assertion must not
        pass by default, or a truncated response would read as a clean run.

        Matching runs in two passes, and no verdict is ever used twice. Text matches are
        resolved first, across all criteria, so a verdict that names its criterion lands on
        that criterion rather than being claimed by an earlier one falling back to position.
        Without that ordering, a response that skips one item shifts a later verdict onto the
        skipped criterion -- which silently reports a violated prohibition as met, on someone
        else's evidence.
        """
        criteria = cls._contract_criteria(contract)
        normalized = [v.criterion.strip().lower() for v in verdicts]
        claimed: Dict[int, int] = {}  # criterion index -> verdict index
        # Verdict indices already claimed, by either pass. Pass 2's fallback candidate for
        # criterion c_index is always verdicts[c_index] -- positional, by definition -- so
        # "is that verdict already claimed" is exactly `c_index in used_indices`.
        used_indices: set = set()

        # Pass 1: a verdict that echoes the criterion text is authoritative, wherever it sits.
        for c_index, (_kind, text) in enumerate(criteria):
            key = text.strip().lower()
            for v_index, v_key in enumerate(normalized):
                if v_index not in used_indices and v_key == key:
                    claimed[c_index] = v_index
                    used_indices.add(v_index)
                    break

        # Pass 2: fall back to position only for criteria still unmatched, and only onto a
        # same-index verdict that nothing claimed and whose kind agrees.
        for c_index, (kind, _text) in enumerate(criteria):
            if c_index in claimed or c_index >= len(verdicts) or c_index in used_indices:
                continue
            if verdicts[c_index].kind == kind:
                claimed[c_index] = c_index
                used_indices.add(c_index)

        aligned: List[CriterionEvaluation] = []

        for index, (kind, text) in enumerate(criteria):
            v_index = claimed.get(index)
            match = verdicts[v_index] if v_index is not None else None

            if match is None:
                logger.warning("No verdict returned for %s criterion %r", kind, text)
                aligned.append(
                    CriterionEvaluation(
                        criterion=text,
                        kind=kind,
                        met=False,
                        evidence="The judge returned no verdict for this criterion.",
                    )
                )
            else:
                aligned.append(
                    CriterionEvaluation(
                        criterion=text,
                        kind=kind,
                        met=match.met,
                        evidence=match.evidence,
                        relevant_turns=match.relevant_turns,
                    )
                )

        return aligned

    @staticmethod
    def _apply_criteria_verdict(result: MetricResult) -> MetricResult:
        """Make a goal-based result pass only when every criterion is met.

        The judge still returns a score, but a score over the threshold with an unmet criterion
        used to pass here while the same miss failed a contract-scored run.
        """
        details = result.details
        if "error" in details:
            return result
        criteria = [CriterionEvaluation(**c) for c in details.get("criteria_evaluations") or []]
        if criteria:
            details.update(_summarize_criteria(criteria))
            details["threshold_applies"] = False
        return result

    def evaluate(
        self,
        conversation_history: ConversationHistory,
        goal: Optional[str] = None,
        instructions: Optional[str] = None,
        contract: Optional[Mapping[str, Any]] = None,
    ) -> MetricResult:
        """
        Evaluate goal achievement in the conversation.

        Args:
            conversation_history: The conversation to evaluate
            goal: Optional explicit goal statement. If not provided, the goal
                  should be inferred from the conversation context.
            instructions: Optional test instructions that specify HOW the test
                  should be conducted (e.g., "send 6 exact messages", "do not stop early").
                  These provide critical context for evaluating whether the goal was
                  properly achieved.
            contract: Optional evaluation contract -- a normalized reading of the test stating
                  what the target must and must not do. When present and it lists at least one
                  criterion, it supersedes ``goal`` and ``instructions``: the conversation is
                  scored against the contract's criteria instead of criteria the judge derives
                  from a free-text goal. This is what makes an adversarial test score the right
                  way round regardless of how its goal was phrased.

        Returns:
            MetricResult with:
                - score: Numeric score (within min_score to max_score)
                - details: Detailed evaluation information including:
                    - score: The numeric score
                    - score_type: "numeric"
                    - prompt: The full evaluation prompt
                    - reason: The LLM's reasoning for the score
                    - is_successful: Whether every criterion was met
                    - threshold_operator: The operator used for threshold comparison
                    - min_score: Minimum possible score
                    - max_score: Maximum possible score
                    - threshold: The threshold value for success
                    - turn_count: Number of turns in the conversation
                    - goal: The goal that was evaluated
                    - instructions: The test instructions (if provided)
                    - criteria_evaluations: CriterionEvaluation dicts (the breakdown)
                    - criteria_total / criteria_met / criteria_failed: Counts
                    - failed_criteria: Text of each unmet criterion
                    - all_criteria_met: Whether all criteria were met
                    - confidence: Confidence level (0.0 to 1.0)

        Raises:
            ValueError: If validation fails
        """
        if _is_scorable_contract(contract):
            return run_sync(
                self._a_evaluate_contract(conversation_history, contract)  # type: ignore[arg-type]
            )

        # Validate inputs
        self._validate_evaluate_inputs(conversation_history, goal)

        # Generate the evaluation prompt
        prompt = self._get_prompt_template(conversation_history, goal, instructions=instructions)

        # Use the shared numeric evaluation pattern with conversational-specific details
        result = self._execute_numeric_evaluation(
            prompt=prompt,
            response_schema=GoalAchievementScoreResponse,
            additional_details={
                "turn_count": self._count_turns(conversation_history),
                "goal": goal or GOAL_DEFAULT,
            },
        )
        return self._apply_criteria_verdict(result)

    async def a_evaluate(
        self,
        conversation_history: ConversationHistory,
        goal: Optional[str] = None,
        instructions: Optional[str] = None,
        contract: Optional[Mapping[str, Any]] = None,
    ) -> MetricResult:
        """Async evaluate using the existing async evaluation pattern."""
        if _is_scorable_contract(contract):
            return await self._a_evaluate_contract(
                conversation_history,
                contract,  # type: ignore[arg-type]
            )

        self._validate_evaluate_inputs(conversation_history, goal)
        prompt = self._get_prompt_template(conversation_history, goal, instructions=instructions)
        result = await self._a_execute_numeric_evaluation(
            prompt=prompt,
            response_schema=GoalAchievementScoreResponse,
            additional_details={
                "turn_count": self._count_turns(conversation_history),
                "goal": goal or GOAL_DEFAULT,
            },
        )
        return self._apply_criteria_verdict(result)

    async def _a_evaluate_contract(
        self,
        conversation_history: ConversationHistory,
        contract: Mapping[str, Any],
    ) -> MetricResult:
        """Score the conversation against a normalized evaluation contract.

        ``score`` is the fraction of criteria the system met, so a partial breach stays
        visible. ``is_successful`` is whether it met **all** of them -- the configured threshold
        does not gate the verdict here, because a test asserts every criterion it lists and one
        miss is still a miss. ``local.py`` prefers a metric's own ``is_successful``
        over the score evaluator, which is what makes that stick.
        """
        prompt = self._get_contract_prompt(conversation_history, contract)
        criteria = self._contract_criteria(contract)

        details = self._get_base_details(prompt)
        details.update(
            {
                "turn_count": self._count_turns(conversation_history),
                "contract": dict(contract),
                "adversarial": bool(contract.get("adversarial")),
                "min_score": self.min_score,
                "max_score": self.max_score,
                "threshold": self.threshold,
                "threshold_applies": False,
                "criteria_total": len(criteria),
            }
        )

        try:
            raw = await self.model.a_generate(
                prompt, schema=ContractComplianceResponse, temperature=JUDGE_TEMPERATURE
            )
            response = ContractComplianceResponse(**raw)  # type: ignore[arg-type]
        except Exception as e:
            return self._handle_evaluation_error(e, details, self.min_score)

        evaluations = self._align_verdicts(contract, response.verdicts)
        total = len(evaluations)

        # An empty contract is filtered out before we get here; guard anyway rather than
        # dividing by zero into a passing verdict.
        if total == 0:
            return self._handle_evaluation_error(
                ValueError("Contract listed no criteria to judge"), details, self.min_score
            )

        summary = _summarize_criteria(evaluations)
        score = self.min_score + summary["criteria_met"] / total * (self.max_score - self.min_score)
        failed = [e for e in evaluations if not e.met]

        details.update(summary)
        details.update(
            {
                "score": score,
                "reason": response.reason or _default_contract_reason(failed, total),
                "confidence": response.confidence,
            }
        )
        return MetricResult(score=score, details=details)

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "GoalAchievementJudge":
        """Create a metric from a dictionary."""
        # Get all field names from the dataclass
        valid_fields = {field.name for field in fields(ConversationalNumericConfig)}

        # Filter config to only include keys that exist in the dataclass
        filtered_config = {k: v for k, v in config.items() if k in valid_fields}

        return cls.from_config(ConversationalNumericConfig(**filtered_config))
