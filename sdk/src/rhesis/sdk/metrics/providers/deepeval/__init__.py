"""DeepEval metrics implementations."""

import os

# Disable deepeval telemetry and environment variable loading
# Must be set before any deepeval imports
os.environ.setdefault("DEEPEVAL_DISABLE_DOTENV", "1")
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

from rhesis.sdk._extras import requires_full_sdk

with requires_full_sdk("DeepEval metrics"):
    from rhesis.sdk.metrics.providers.deepeval.factory import DeepEvalMetricFactory
    from rhesis.sdk.metrics.providers.deepeval.metric_base import DeepEvalMetricBase

__all__ = [
    "DeepEvalMetricBase",
    "DeepEvalMetricFactory",
    "DeepEvalAnswerRelevancy",
    "DeepEvalBias",
    "DeepEvalFaithfulness",
    "DeepEvalContextualRelevancy",
    "DeepEvalContextualPrecision",
    "DeepEvalContextualRecall",
    "DeepEvalMisuse",
    "DeepEvalNonAdvice",
    "DeepEvalPIILeakage",
    "DeepEvalRoleViolation",
    "DeepEvalToxicity",
    "DeepTeamIllegal",
    "DeepTeamSafety",
    # Conversational metrics
    "DeepEvalTurnRelevancy",
    "DeepEvalRoleAdherence",
    "DeepEvalKnowledgeRetention",
    "DeepEvalConversationCompleteness",
    "DeepEvalGoalAccuracy",
    "DeepEvalToolUse",
]


def __getattr__(name: str):
    """Lazy load deepeval metric classes to avoid eager imports."""
    if name in __all__:
        # Import from metrics module
        if name in [
            "DeepEvalAnswerRelevancy",
            "DeepEvalBias",
            "DeepEvalFaithfulness",
            "DeepEvalContextualRelevancy",
            "DeepEvalContextualPrecision",
            "DeepEvalContextualRecall",
            "DeepEvalMisuse",
            "DeepEvalNonAdvice",
            "DeepEvalPIILeakage",
            "DeepEvalRoleViolation",
            "DeepEvalToxicity",
            "DeepTeamIllegal",
            "DeepTeamSafety",
        ]:
            from rhesis.sdk.metrics.providers.deepeval import metrics

            return getattr(metrics, name)

        # Import from conversational_metrics module
        if name in [
            "DeepEvalTurnRelevancy",
            "DeepEvalRoleAdherence",
            "DeepEvalKnowledgeRetention",
            "DeepEvalConversationCompleteness",
            "DeepEvalGoalAccuracy",
            "DeepEvalToolUse",
        ]:
            from rhesis.sdk.metrics.providers.deepeval import conversational_metrics

            return getattr(conversational_metrics, name)

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
