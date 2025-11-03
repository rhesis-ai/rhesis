"""
Goal evaluation module for Penelope.

This module handles goal progress evaluation using either SDK metrics
or interim LLM-based evaluation.
"""

import logging
from typing import Any, List, Optional

from rhesis.penelope.context import GoalProgress, TestState, Turn
from rhesis.penelope.prompts import GOAL_EVALUATION_PROMPT
from rhesis.penelope.schemas import SimpleGoalEval
from rhesis.sdk.models.base import BaseLLM

logger = logging.getLogger(__name__)


class GoalEvaluator:
    """
    Handles goal progress evaluation for test execution.

    Supports two evaluation methods:
    1. SDK multi-turn metrics (when available)
    2. Interim LLM-based evaluation using structured outputs

    Args:
        model: Language model for LLM-based evaluation
        goal_metric: Optional SDK multi-turn metric for evaluation
    """

    def __init__(
        self,
        model: BaseLLM,
        goal_metric: Optional[Any] = None,
    ):
        """Initialize the goal evaluator."""
        self.model = model
        self.goal_metric = goal_metric

    def evaluate_progress(
        self,
        state: TestState,
        goal: str,
    ) -> GoalProgress:
        """
        Evaluate progress toward the test goal.

        Uses SDK multi-turn metrics if available (self.goal_metric),
        otherwise uses interim LLM-based evaluation.

        Args:
            state: Current test state
            goal: The test goal

        Returns:
            GoalProgress with evaluation
        """
        # Need at least some conversation to evaluate
        if not state.turns or len(state.turns) < 2:
            return GoalProgress(
                goal_achieved=False,
                goal_impossible=False,
                confidence=0.0,
                reasoning="Insufficient conversation for evaluation",
            )

        # === Path 1: Use SDK Metric (when available) ===
        if self.goal_metric:
            return self._evaluate_with_sdk_metric(state, goal)

        # === Path 2: Interim Simple LLM Evaluation ===
        return self._evaluate_with_simple_llm(state, goal)

    def _evaluate_with_sdk_metric(
        self,
        state: TestState,
        goal: str,
    ) -> GoalProgress:
        """
        Use SDK multi-turn metric for evaluation.

        This path is used when self.goal_metric is provided (future SDK integration).

        Args:
            state: Current test state
            goal: The test goal

        Returns:
            GoalProgress converted from SDK MetricResult
        """
        # Convert Penelope's conversation to SDK format
        conversation = self._to_conversation_format(state.turns)

        # Evaluate using the metric (already checked for None in caller)
        assert self.goal_metric is not None  # Type narrowing
        result = self.goal_metric.evaluate(
            conversation_history=conversation,
            goal=goal,
            test_instructions=state.context.instructions,
            context=state.context.context,
        )

        # Convert MetricResult to GoalProgress
        details = result.details

        # Determine if goal is impossible
        is_impossible = (
            not details.get("is_successful", False)
            and details.get("confidence", 0.0) > 0.8
            and len(state.turns) >= 5
        )

        return GoalProgress(
            goal_achieved=details.get("is_successful", False),
            goal_impossible=is_impossible,
            confidence=details.get("confidence", 0.5),
            reasoning=details.get("reasoning", ""),
            findings=details.get("evidence", []),
        )

    def _evaluate_with_simple_llm(
        self,
        state: TestState,
        goal: str,
    ) -> GoalProgress:
        """
        INTERIM: Simple LLM-based goal evaluation.

        This is a temporary solution until SDK multi-turn metrics are ready.
        Uses a simple prompt + structured output to evaluate goal achievement.

        Args:
            state: Current test state
            goal: The test goal

        Returns:
            GoalProgress with LLM evaluation
        """
        # Format conversation for evaluation
        conversation = self._format_conversation_for_eval(state.turns)

        # Log the formatted conversation for debugging
        logger.debug(f"Evaluating conversation with {len(state.turns)} Penelope turns")
        logger.debug(f"Formatted conversation:\n{conversation}")

        # Build evaluation prompt using versioned template
        prompt = GOAL_EVALUATION_PROMPT.render(
            goal=goal,
            instructions=state.context.instructions or "None provided",
            conversation=conversation,
        )

        try:
            # Get structured response from LLM
            response = self.model.generate(prompt, schema=SimpleGoalEval)
            # Type narrowing: response should be dict when schema is provided
            if not isinstance(response, dict):
                raise ValueError(f"Expected dict response, got {type(response)}")
            result = SimpleGoalEval(**response)

            # Log detailed evaluation for transparency
            logger.debug(f"Turn count reported by LLM: {result.turn_count}")
            logger.debug("Criterion-by-criterion evaluation:")
            for i, criterion in enumerate(result.criteria_evaluations, 1):
                status = "✓" if criterion.met else "✗"
                logger.debug(f"  {i}. {status} {criterion.criterion}")
                logger.debug(f"     Evidence: {criterion.evidence}")
            logger.debug(f"All criteria met: {result.all_criteria_met}")
            logger.debug(f"Goal achieved: {result.goal_achieved}")

            # Build detailed findings from criteria
            findings = []
            for criterion in result.criteria_evaluations:
                status = "MET" if criterion.met else "NOT MET"
                findings.append(f"[{status}] {criterion.criterion}: {criterion.evidence}")

            # Add overall evidence
            findings.extend(result.evidence)

            return GoalProgress(
                goal_achieved=result.goal_achieved,
                goal_impossible=False,
                confidence=result.confidence,
                reasoning=f"Turn count: {result.turn_count}. {result.reasoning}",
                findings=findings,
            )

        except Exception as e:
            logger.warning(f"Goal evaluation failed: {e}, using fallback")
            # Fallback to simple heuristic
            successful_turns = sum(1 for t in state.turns if t.tool_result.get("success", False))
            return GoalProgress(
                goal_achieved=False,
                goal_impossible=False,
                confidence=0.3,
                reasoning=(
                    f"Evaluation failed: {e}. Observed {successful_turns} successful turns."
                ),
            )

    def _format_conversation_for_eval(self, turns: List[Turn]) -> str:
        """
        Format Penelope turns as a readable conversation for evaluation.

        Args:
            turns: List of Turn objects from test execution

        Returns:
            Formatted conversation string
        """
        lines = []
        for turn in turns:
            if turn.tool_name == "send_message_to_target":
                # Extract message from tool arguments
                msg = turn.tool_arguments.get("message", "")
                if msg:
                    lines.append(f"USER: {msg}")

                # Extract response from tool result
                result = turn.tool_result
                if isinstance(result, dict) and result.get("success"):
                    resp = result.get("output", {})
                    resp_text = resp.get("response", "") if isinstance(resp, dict) else str(resp)
                    if resp_text:
                        lines.append(f"ASSISTANT: {resp_text}")

        return "\n".join(lines)

    def _to_conversation_format(self, turns: List[Turn]) -> Any:
        """
        Convert Penelope's Turn objects to SDK ConversationHistory.
        Only used when SDK metrics are available.

        Args:
            turns: List of Turn objects from test execution

        Returns:
            ConversationHistory object (when SDK is available)
        """
        # Lazy import to avoid dependency before SDK is ready
        try:
            from rhesis.sdk.metrics.types import (  # type: ignore[import-not-found]
                ConversationHistory,
                ConversationTurn,
            )
        except ImportError:
            logger.error("SDK metrics not available - cannot convert conversation format")
            return None

        # Convert turns to ConversationTurn objects
        sdk_turns = []
        for turn in turns:
            # Only convert send_message_to_target turns
            if turn.tool_name == "send_message_to_target":
                msg = turn.tool_arguments.get("message", "")
                result = turn.tool_result

                if isinstance(result, dict) and result.get("success"):
                    resp = result.get("output", {})
                    resp_text = resp.get("response", "") if isinstance(resp, dict) else str(resp)

                    sdk_turns.append(
                        ConversationTurn(
                            user_message=msg,
                            assistant_message=resp_text,
                            metadata={
                                "turn_number": turn.turn_number,
                                "timestamp": turn.timestamp.isoformat(),
                            },
                        )
                    )

        return ConversationHistory(turns=sdk_turns)

