"""
Backend metrics orchestration - uses SDK metrics via adapter layer.

This module provides:
- MetricEvaluator: Orchestrates batch evaluation with parallel execution
- ScoreEvaluator: Evaluates scores against thresholds
- Adapter: Bridges database models to SDK metrics
- Re-exports: SDK metrics for convenience
"""

# Backend-specific orchestration
# Re-export SDK classes for convenience
from rhesis.sdk.metrics import (
    BaseMetric,
    CategoricalJudge,
    # DeepEval metrics
    DeepEvalAnswerRelevancy,
    DeepEvalContextualPrecision,
    DeepEvalContextualRecall,
    DeepEvalContextualRelevancy,
    DeepEvalFaithfulness,
    MetricConfig,
    MetricFactory,
    MetricResult,
    # Native metrics (renamed)
    NumericJudge,
    # Ragas metrics
    RagasAnswerAccuracy,
    RagasAspectCritic,
    RagasContextRelevance,
    RagasFaithfulness,
)

# Adapter layer (DB → SDK)
from .adapters import (
    create_metric,
    create_metric_from_config,
    create_metric_from_db_model,
)
from .constants import (
    OPERATOR_MAP,
    VALID_OPERATORS_BY_SCORE_TYPE,
    ScoreType,
    ThresholdOperator,
)
from .evaluator import MetricEvaluator as Evaluator
from .score_evaluator import ScoreEvaluator
from .utils import diagnose_invalid_metric, run_evaluation

__all__ = [
    # Backend orchestration
    "Evaluator",
    "ScoreEvaluator",
    "run_evaluation",
    "diagnose_invalid_metric",
    # Adapter layer
    "create_metric_from_db_model",
    "create_metric_from_config",
    "create_metric",
    # Types and utilities
    "ScoreType",
    "ThresholdOperator",
    "OPERATOR_MAP",
    "VALID_OPERATORS_BY_SCORE_TYPE",
    # SDK re-exports
    "BaseMetric",
    "MetricConfig",
    "MetricResult",
    "MetricFactory",
    "NumericJudge",
    "CategoricalJudge",
    "RagasAnswerAccuracy",
    "RagasAspectCritic",
    "RagasContextRelevance",
    "RagasFaithfulness",
    "DeepEvalAnswerRelevancy",
    "DeepEvalFaithfulness",
    "DeepEvalContextualPrecision",
    "DeepEvalContextualRecall",
    "DeepEvalContextualRelevancy",
]
