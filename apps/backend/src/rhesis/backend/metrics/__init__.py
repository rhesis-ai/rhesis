"""Metrics for evaluating RAG and generation systems."""

from .base import BaseMetric, MetricConfig, MetricResult
from .config.loader import MetricConfigLoader
from .evaluator import MetricEvaluator as Evaluator
from .factory import MetricFactory
from .score_evaluator import ScoreEvaluator
from .types import ScoreType, ThresholdOperator, OPERATOR_MAP, VALID_OPERATORS_BY_SCORE_TYPE
from .utils import run_evaluation, diagnose_invalid_metric
from .rhesis import (  # Re-export Rhesis metrics
    RhesisMetricBase,
    RhesisMetricFactory,
    RhesisPromptMetric,
)
from .deepeval import (  # Re-export DeepEval metrics
    DeepEvalMetricBase,
    DeepEvalMetricFactory,
    DeepEvalAnswerRelevancy,
    DeepEvalFaithfulness,
    DeepEvalContextualRelevancy,
    DeepEvalContextualPrecision,
    DeepEvalContextualRecall,
)
from .ragas import (  # Re-export Ragas metrics
    RagasMetricBase,
    RagasMetricFactory,
    RagasAnswerRelevancy,
    RagasContextualPrecision,
)

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
    
    # DeepEval metrics
    "DeepEvalMetricBase",
    "DeepEvalMetricFactory",
    "DeepEvalAnswerRelevancy",
    "DeepEvalFaithfulness",
    "DeepEvalContextualRelevancy",
    "DeepEvalContextualPrecision",
    "DeepEvalContextualRecall",
    
    # Ragas metrics
    "RagasMetricBase",
    "RagasMetricFactory",
    "RagasAnswerRelevancy",
    "RagasContextualPrecision",
]
