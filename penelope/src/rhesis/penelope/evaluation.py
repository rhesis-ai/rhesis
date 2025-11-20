"""
Goal evaluation module for Penelope.

Uses SDK's GoalAchievementJudge for sophisticated conversation evaluation.
No conversion needed - Penelope maintains conversation in SDK format natively.
"""

import logging
from typing import TYPE_CHECKING

from rhesis.sdk.metrics.base import MetricResult

if TYPE_CHECKING:
    from rhesis.penelope.context import TestState
    from rhesis.sdk.metrics.providers.native import GoalAchievementJudge

logger = logging.getLogger(__name__)


class GoalEvaluator:
    """
    Evaluates goal progress using SDK's GoalAchievementJudge.

    Args:
        goal_metric: SDK GoalAchievementJudge for evaluation
    """

    def __init__(self, goal_metric: "GoalAchievementJudge"):
        """Initialize with SDK metric."""
        self.goal_metric = goal_metric

    def evaluate(self, state: "TestState", goal: str, instructions: str = "") -> MetricResult:
        """
        Evaluate goal achievement using SDK metric.

        Uses state.conversation which is maintained natively in SDK format,
        so no conversion is needed.

        Args:
            state: Current test state with conversation
            goal: The test goal
            instructions: Optional test instructions that specify HOW the test should be conducted.
                         These provide critical context for evaluating whether the goal was
                         properly achieved.

        Returns:
            SDK MetricResult (no conversion!)
        """
        # Need minimum conversation
        if len(state.conversation) < 1:
            # Return minimal result for insufficient data
            return MetricResult(
                score=0.0,
                details={
                    "is_successful": False,
                    "confidence": 0.0,
                    "reason": "Insufficient conversation for evaluation (< 1 turn)",
                },
            )

        # Direct evaluation - zero conversion!
        logger.debug(f"Evaluating conversation with {len(state.conversation)} messages")
        return self.goal_metric.evaluate(
            conversation_history=state.conversation,
            goal=goal,
            instructions=instructions,
        )
