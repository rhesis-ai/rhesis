"""Metrics for evaluating RAG and generation systems."""

from rhesis.sdk.metrics.base import BaseMetric, MetricConfig, MetricResult
from rhesis.sdk.metrics.config.loader import MetricConfigLoader
from rhesis.sdk.metrics.constants import (
    OPERATOR_MAP,
    VALID_OPERATORS_BY_SCORE_TYPE,
    ScoreType,
    ThresholdOperator,
)
from rhesis.sdk.metrics.evaluator import MetricEvaluator as Evaluator
from rhesis.sdk.metrics.factory import MetricFactory
from rhesis.sdk.metrics.providers.deepeval.factory import DeepEvalMetricFactory
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
)
from rhesis.sdk.metrics.providers.native import (  # Re-export Rhesis metrics
    RhesisMetricFactory,
    RhesisPromptMetricCategorical,
    RhesisPromptMetricNumeric,
)
from rhesis.sdk.metrics.providers.ragas.metric_base import RagasMetricBase
from rhesis.sdk.metrics.providers.ragas.metrics import (
    RagasAnswerAccuracy,
    RagasAspectCritic,
    RagasContextRelevance,
    RagasFaithfulness,
)
from rhesis.sdk.metrics.score_evaluator import ScoreEvaluator
from rhesis.sdk.metrics.utils import diagnose_invalid_metric, run_evaluation

__all__ = [
    # Base metrics
    "BaseMetric",
    "MetricConfig",
    "MetricResult",
    "MetricConfigLoader",
    "MetricFactory",
    # Evaluation
    "Evaluator",
    "ScoreEvaluator",
    "run_evaluation",
    # Types and utilities
    "ScoreType",
    "ThresholdOperator",
    "OPERATOR_MAP",
    "VALID_OPERATORS_BY_SCORE_TYPE",
    "diagnose_invalid_metric",
    # DeepEval metrics
    "DeepEvalMetricFactory",
    "DeepEvalAnswerRelevancy",
    "DeepEvalBias",
    "DeepEvalContextualPrecision",
    "DeepEvalContextualRecall",
    "DeepEvalContextualRelevancy",
    "DeepEvalFaithfulness",
    "DeepEvalBias",
    "DeepEvalMisuse",
    "DeepEvalNonAdvice",
    "DeepEvalPIILeakage",
    "DeepEvalRoleViolation",
    "DeepEvalToxicity",
    # Rhesis metrics
    "RhesisMetricFactory",
    "RhesisPromptMetricCategorical",
    "RhesisPromptMetricNumeric",
    # Ragas metrics
    "RagasMetricBase",
    "RagasAnswerAccuracy",
    "RagasAspectCritic",
    "RagasContextRelevance",
    "RagasFaithfulness",
]
