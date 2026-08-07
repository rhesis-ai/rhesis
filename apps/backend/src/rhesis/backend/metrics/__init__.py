"""
Backend metrics orchestration - uses SDK metrics directly.

This module provides:
- MetricEvaluator: Orchestrates batch evaluation with parallel execution
- ScoreEvaluator: Evaluates scores against thresholds
- Re-exports: SDK metrics for convenience
"""

# Backend-specific orchestration
# Re-export SDK classes for convenience
from rhesis.backend.app.schemas.metric_types import (
    OPERATOR_MAP,
    VALID_OPERATORS_BY_SCORE_TYPE,
    ScoreType,
    ThresholdOperator,
)
from rhesis.sdk.metrics import (
    BaseMetric,
    CategoricalJudge,
    MetricConfig,
    MetricFactory,
    MetricResult,
    # Native metrics (renamed)
    NumericJudge,
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


_LAZY_SDK_NAMES = frozenset(
    {
        # Ragas metrics (pulls in ragas/transformers/torch/datasets on first use)
        "RagasAnswerAccuracy",
        "RagasAspectCritic",
        "RagasContextRelevance",
        "RagasFaithfulness",
        # DeepEval metrics
        "DeepEvalAnswerRelevancy",
        "DeepEvalFaithfulness",
        "DeepEvalContextualPrecision",
        "DeepEvalContextualRecall",
        "DeepEvalContextualRelevancy",
    }
)


def __getattr__(name: str):
    """Lazy load ragas/deepeval metric classes to avoid eager imports."""
    if name in _LAZY_SDK_NAMES:
        from rhesis.sdk.metrics import __getattr__ as sdk_getattr

        return sdk_getattr(name)

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
