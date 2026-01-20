"""Metrics for evaluating RAG and generation systems."""

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
from rhesis.sdk.metrics.providers.native import (  # Re-export Rhesis metrics
    CategoricalJudge,
    ConversationalJudge,
    CriterionEvaluation,
    GoalAchievementJudge,
    GoalAchievementScoreResponse,
    ImageJudge,
    NumericJudge,
    RhesisMetricFactory,
)
from rhesis.sdk.metrics.providers.ragas.metric_base import RagasMetricBase
from rhesis.sdk.metrics.providers.ragas.metrics import (
    RagasAnswerAccuracy,
    RagasAspectCritic,
    RagasContextRelevance,
    RagasFaithfulness,
)

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
    # Evaluation
    # Types and utilities
    "ScoreType",
    "ThresholdOperator",
    "OPERATOR_MAP",
    "VALID_OPERATORS_BY_SCORE_TYPE",
    # DeepEval
    "DeepEvalMetricFactory",
    # DeepEval metrics
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
    # DeepEval conversational metrics
    "DeepEvalTurnRelevancy",
    "DeepEvalRoleAdherence",
    "DeepEvalKnowledgeRetention",
    "DeepEvalConversationCompleteness",
    "DeepEvalGoalAccuracy",
    "DeepEvalToolUse",
    # Rhesis
    "RhesisMetricFactory",
    # Rhesis metrics
    "CategoricalJudge",
    "NumericJudge",
    "ImageJudge",
    # Rhesis conversational metrics
    "ConversationalJudge",
    "GoalAchievementJudge",
    "CriterionEvaluation",
    "GoalAchievementScoreResponse",
    # Ragas
    "RagasMetricBase",
    # Ragas metrics
    "RagasAnswerAccuracy",
    "RagasAspectCritic",
    "RagasContextRelevance",
    "RagasFaithfulness",
]


def __getattr__(name: str):
    """Lazy load deepeval metric classes to avoid eager imports."""
    # DeepEval metrics and factory
    deepeval_items = [
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
    ]

    if name in deepeval_items:
        from rhesis.sdk.metrics.providers import deepeval

        return getattr(deepeval, name)

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
