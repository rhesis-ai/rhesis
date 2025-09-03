"""Metrics for evaluating RAG and generation systems."""

from .base import BaseMetric, MetricConfig, MetricResult
from .config.loader import MetricConfigLoader
from .constants import OPERATOR_MAP, VALID_OPERATORS_BY_SCORE_TYPE, ScoreType, ThresholdOperator
from .evaluator import MetricEvaluator as Evaluator
from .factory import MetricFactory

# Lazy import to avoid circular dependencies
# from .deepeval import (  # Re-export DeepEval metrics
#     DeepEvalMetricBase,
#     DeepEvalMetricFactory,
#     DeepEvalAnswerRelevancy,
#     DeepEvalFaithfulness,
#     DeepEvalContextualRelevancy,
#     DeepEvalContextualPrecision,
#     DeepEvalContextualRecall,
# )
from rhesis.sdk.metrics.providers.ragas import (  # Re-export Ragas metrics
    RagasAnswerRelevancy,
    RagasContextualPrecision,
    RagasMetricBase,
    RagasMetricFactory,
)
from rhesis.sdk.metrics.providers.native import (  # Re-export Rhesis metrics
    RhesisMetricBase,
    RhesisMetricFactory,
    RhesisPromptMetric,
)
from .score_evaluator import ScoreEvaluator
from .utils import diagnose_invalid_metric, run_evaluation

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
    # Rhesis metrics
    "RhesisMetricBase",
    "RhesisMetricFactory",
    "RhesisPromptMetric",
    # DeepEval metrics (commented out to avoid circular imports)
    # "DeepEvalMetricBase",
    # "DeepEvalMetricFactory",
    # "DeepEvalAnswerRelevancy",
    # "DeepEvalFaithfulness",
    # "DeepEvalContextualRelevancy",
    # "DeepEvalContextualPrecision",
    # "DeepEvalContextualRecall",
    # Ragas metrics
    "RagasMetricBase",
    "RagasMetricFactory",
    "RagasAnswerRelevancy",
    "RagasContextualPrecision",
]
