"""Metrics for evaluating RAG and generation systems."""

from rhesis.sdk.metrics.base import BaseMetric, MetricConfig, MetricResult
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
from rhesis.sdk.metrics.providers.deepeval.factory import DeepEvalMetricFactory
from rhesis.sdk.metrics.providers.deepeval.conversational_metrics import (
    DeepEvalTurnRelevancy,
)
from rhesis.sdk.metrics.providers.deepeval.metrics import (
    DeepEvalAnswerRelevancy,
    DeepEvalBias,
    DeepEvalContextualPrecision,
    DeepEvalContextualRecall,
    DeepEvalContextualRelevancy,
    DeepEvalFaithfulness,
    DeepEvalMisuse,
    DeepEvalNonAdvice,
    DeepEvalPIILeakage,
    DeepEvalRoleViolation,
    DeepEvalToxicity,
    DeepTeamIllegal,
    DeepTeamSafety,
)
from rhesis.sdk.metrics.providers.native import (  # Re-export Rhesis metrics
    CategoricalJudge,
    ConversationalJudge,
    CriterionEvaluation,
    GoalAchievementJudge,
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
    # Rhesis
    "RhesisMetricFactory",
    # Rhesis metrics
    "CategoricalJudge",
    "NumericJudge",
    # Rhesis conversational metrics
    "ConversationalJudge",
    "GoalAchievementJudge",
    "CriterionEvaluation",
    # Ragas
    "RagasMetricBase",
    # Ragas metrics
    "RagasAnswerAccuracy",
    "RagasAspectCritic",
    "RagasContextRelevance",
    "RagasFaithfulness",
]
