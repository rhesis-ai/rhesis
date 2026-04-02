"""Metrics for evaluating RAG and generation systems.

Heavy backends (native judges, Ragas, DeepEval metric classes) load on first use.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from rhesis.sdk.metrics.base import BaseMetric, MetricConfig, MetricResult, MetricScope
from rhesis.sdk.metrics.config.loader import MetricConfigLoader
from rhesis.sdk.metrics.constants import (
    OPERATOR_MAP,
    VALID_OPERATORS_BY_SCORE_TYPE,
    ScoreType,
    ThresholdOperator,
)
from rhesis.sdk.metrics.conversational import (
    AssistantMessage,
    ConversationalMetricBase,
    ConversationHistory,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from rhesis.sdk.metrics.factory import MetricFactory

if TYPE_CHECKING:
    from rhesis.sdk.metrics.providers.native.categorical_judge import CategoricalJudge
    from rhesis.sdk.metrics.providers.native.conversational_judge import ConversationalJudge
    from rhesis.sdk.metrics.providers.native.factory import RhesisMetricFactory
    from rhesis.sdk.metrics.providers.native.goal_achievement_judge import (
        CriterionEvaluation,
        GoalAchievementJudge,
        GoalAchievementScoreResponse,
    )
    from rhesis.sdk.metrics.providers.native.numeric_judge import NumericJudge
    from rhesis.sdk.metrics.providers.ragas.metric_base import RagasMetricBase
    from rhesis.sdk.metrics.providers.ragas.metrics import (
        RagasAnswerAccuracy,
        RagasAspectCritic,
        RagasContextRelevance,
        RagasFaithfulness,
    )

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    # Native — per-module import avoids loading all judges when only one is needed
    "CategoricalJudge": (
        "rhesis.sdk.metrics.providers.native.categorical_judge",
        "CategoricalJudge",
    ),
    "ConversationalJudge": (
        "rhesis.sdk.metrics.providers.native.conversational_judge",
        "ConversationalJudge",
    ),
    "NumericJudge": ("rhesis.sdk.metrics.providers.native.numeric_judge", "NumericJudge"),
    "GoalAchievementJudge": (
        "rhesis.sdk.metrics.providers.native.goal_achievement_judge",
        "GoalAchievementJudge",
    ),
    "CriterionEvaluation": (
        "rhesis.sdk.metrics.providers.native.goal_achievement_judge",
        "CriterionEvaluation",
    ),
    "GoalAchievementScoreResponse": (
        "rhesis.sdk.metrics.providers.native.goal_achievement_judge",
        "GoalAchievementScoreResponse",
    ),
    "RhesisMetricFactory": (
        "rhesis.sdk.metrics.providers.native.factory",
        "RhesisMetricFactory",
    ),
    # Ragas
    "RagasMetricBase": (
        "rhesis.sdk.metrics.providers.ragas.metric_base",
        "RagasMetricBase",
    ),
    "RagasAnswerAccuracy": (
        "rhesis.sdk.metrics.providers.ragas.metrics",
        "RagasAnswerAccuracy",
    ),
    "RagasAspectCritic": (
        "rhesis.sdk.metrics.providers.ragas.metrics",
        "RagasAspectCritic",
    ),
    "RagasContextRelevance": (
        "rhesis.sdk.metrics.providers.ragas.metrics",
        "RagasContextRelevance",
    ),
    "RagasFaithfulness": (
        "rhesis.sdk.metrics.providers.ragas.metrics",
        "RagasFaithfulness",
    ),
}

_DEEPEVAL_NAMES = frozenset(
    {
        "DeepEvalMetricFactory",
        "DeepEvalAnswerRelevancy",
        "DeepEvalBias",
        "DeepEvalContextualPrecision",
        "DeepEvalContextualRecall",
        "DeepEvalContextualRelevancy",
        "DeepEvalFaithfulness",
        "DeepEvalMisuse",
        "DeepEvalNonAdvice",
        "DeepEvalPIILeakage",
        "DeepEvalRoleViolation",
        "DeepEvalToxicity",
        "DeepTeamSafety",
        "DeepTeamIllegal",
        "DeepEvalTurnRelevancy",
        "DeepEvalRoleAdherence",
        "DeepEvalKnowledgeRetention",
        "DeepEvalConversationCompleteness",
        "DeepEvalGoalAccuracy",
        "DeepEvalToolUse",
    }
)


def __getattr__(name: str):
    spec = _LAZY_EXPORTS.get(name)
    if spec is not None:
        module_name, attr_name = spec
        mod = importlib.import_module(module_name)
        return getattr(mod, attr_name)
    if name in _DEEPEVAL_NAMES:
        from rhesis.sdk.metrics.providers import deepeval

        return getattr(deepeval, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)


__all__ = [
    # Base metrics
    "BaseMetric",
    "MetricConfig",
    "MetricResult",
    "MetricScope",
    "MetricConfigLoader",
    "MetricFactory",
    # Conversational metrics
    "ConversationalMetricBase",
    "ConversationHistory",
    "UserMessage",
    "AssistantMessage",
    "ToolMessage",
    "SystemMessage",
    # Types and utilities
    "ScoreType",
    "ThresholdOperator",
    "OPERATOR_MAP",
    "VALID_OPERATORS_BY_SCORE_TYPE",
    # DeepEval
    "DeepEvalMetricFactory",
    "DeepEvalAnswerRelevancy",
    "DeepEvalBias",
    "DeepEvalContextualPrecision",
    "DeepEvalContextualRecall",
    "DeepEvalContextualRelevancy",
    "DeepEvalFaithfulness",
    "DeepEvalMisuse",
    "DeepEvalNonAdvice",
    "DeepEvalPIILeakage",
    "DeepEvalRoleViolation",
    "DeepEvalToxicity",
    "DeepTeamSafety",
    "DeepTeamIllegal",
    "DeepEvalTurnRelevancy",
    "DeepEvalRoleAdherence",
    "DeepEvalKnowledgeRetention",
    "DeepEvalConversationCompleteness",
    "DeepEvalGoalAccuracy",
    "DeepEvalToolUse",
    # Rhesis native
    "RhesisMetricFactory",
    "CategoricalJudge",
    "NumericJudge",
    "ConversationalJudge",
    "GoalAchievementJudge",
    "CriterionEvaluation",
    "GoalAchievementScoreResponse",
    # Ragas
    "RagasMetricBase",
    "RagasAnswerAccuracy",
    "RagasAspectCritic",
    "RagasContextRelevance",
    "RagasFaithfulness",
]
