"""Metrics for evaluating RAG and generation systems."""

from rhesis.sdk.metrics.providers.native import (  # Re-export Rhesis metrics
    RhesisMetricBase,
    RhesisMetricFactory,
    RhesisPromptMetricCategorical,
    RhesisPromptMetricNumeric,
)
from rhesis.sdk.metrics.providers.ragas import (  # Re-export Ragas metrics
    RagasAnswerRelevancy,
    RagasContextualPrecision,
    RagasMetricBase,
    RagasMetricFactory,
)

from .base import BaseMetric, MetricConfig, MetricResult
from .config.loader import MetricConfigLoader
from .constants import OPERATOR_MAP, VALID_OPERATORS_BY_SCORE_TYPE, ScoreType, ThresholdOperator
from .evaluator import MetricEvaluator as Evaluator
from .factory import MetricFactory
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
    "RhesisPromptMetricCategorical",
    "RhesisPromptMetricNumeric",
    # Ragas metrics
    "RagasMetricBase",
    "RagasMetricFactory",
    "RagasAnswerRelevancy",
    "RagasContextualPrecision",
]
