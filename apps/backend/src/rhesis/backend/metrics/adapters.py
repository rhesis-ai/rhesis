"""
Adapter layer for bridging backend database models to SDK metrics.

This module provides translation between:
- Backend database Metric models → SDK metric instances
- Backend class naming → SDK class naming (handles RhesisPromptMetric split)
- Backend metric configs (dicts) → SDK metric instances

The adapter pattern allows the backend to continue using its own evaluators
while leveraging SDK metric implementations, and makes it easy to handle
future SDK naming changes (e.g., NumericJudge, CategoricalJudge).
"""

from typing import Any, Dict, Optional, Union
from uuid import UUID

from rhesis.backend.app.models.metric import Metric as MetricModel
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.sdk.metrics import BaseMetric, MetricFactory

# ============================================================================
# CLASS NAME MAPPING
# ============================================================================
# This mapping handles the split of backend's single RhesisPromptMetric class
# into SDK's separate Numeric and Categorical classes.
#
# FUTURE: When SDK renames to NumericJudge/CategoricalJudge, update here:
# "numeric": "NumericJudge",
# "categorical": "CategoricalJudge",
# ============================================================================

CLASS_NAME_MAP = {
    "RhesisPromptMetric": {
        # Current SDK names (as of Oct 2025)
        "numeric": "RhesisPromptMetricNumeric",
        "categorical": "RhesisPromptMetricCategorical",
        "binary": "RhesisPromptMetricCategorical",  # Binary uses categorical
        # FUTURE: Replace with new SDK names when ready
        # "numeric": "NumericJudge",
        # "categorical": "CategoricalJudge",
        # "binary": "CategoricalJudge",
    }
}

# Backend type to SDK framework mapping
BACKEND_TO_FRAMEWORK_MAP = {
    "rhesis": "rhesis",
    "deepeval": "deepeval",
    "ragas": "ragas",
    "custom": "rhesis",  # Custom metrics use rhesis framework
    "custom-code": "rhesis",
    "custom-prompt": "rhesis",
    "framework": "deepeval",  # Legacy fallback
}


# ============================================================================
# ADAPTER FUNCTIONS
# ============================================================================


def get_sdk_class_name(backend_class_name: str, score_type: Optional[str] = None) -> str:
    """
    Map backend class name to SDK class name.

    This function handles the split of RhesisPromptMetric into separate
    SDK classes based on score_type.

    Args:
        backend_class_name: Class name from database (e.g., "RhesisPromptMetric")
        score_type: Score type ("numeric", "categorical", "binary")

    Returns:
        SDK class name (e.g., "RhesisPromptMetricNumeric")

    Examples:
        >>> get_sdk_class_name("RhesisPromptMetric", "numeric")
        'RhesisPromptMetricNumeric'

        >>> get_sdk_class_name("RhesisPromptMetric", "categorical")
        'RhesisPromptMetricCategorical'

        >>> get_sdk_class_name("RagasAnswerRelevancy")
        'RagasAnswerRelevancy'
    """
    # Handle RhesisPromptMetric split
    if backend_class_name == "RhesisPromptMetric":
        if not score_type:
            logger.warning(f"RhesisPromptMetric requires score_type, defaulting to 'numeric'")
            score_type = "numeric"

        sdk_class_name = CLASS_NAME_MAP["RhesisPromptMetric"].get(
            score_type, "RhesisPromptMetricNumeric"
        )
        logger.debug(f"Mapped {backend_class_name} (score_type={score_type}) → {sdk_class_name}")
        return sdk_class_name

    # All other metrics use their class name directly
    return backend_class_name


def map_backend_type_to_framework(backend_type: Optional[str]) -> str:
    """
    Map backend type to SDK framework name.

    Args:
        backend_type: Backend type from database (e.g., "rhesis", "deepeval")

    Returns:
        SDK framework name
    """
    if not backend_type:
        logger.debug("No backend_type provided, defaulting to 'rhesis'")
        return "rhesis"

    framework = BACKEND_TO_FRAMEWORK_MAP.get(backend_type, backend_type)
    logger.debug(f"Mapped backend_type '{backend_type}' → framework '{framework}'")
    return framework


def build_metric_params_from_model(
    metric_model: MetricModel, organization_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract SDK-compatible parameters from database Metric model.

    Args:
        metric_model: Database Metric model instance
        organization_id: Optional organization ID for model lookup

    Returns:
        Dictionary of parameters for SDK metric constructor
    """
    params = {
        "name": metric_model.name or f"Metric_{metric_model.id}",
        "description": metric_model.description,
    }

    # Add prompt-related fields (all required for RhesisPromptMetric by SDK factory)
    # Provide defaults for metrics that don't have these configured
    params["evaluation_prompt"] = (
        metric_model.evaluation_prompt
        or f"Evaluate the quality of the output for {params['name']}."
    )
    params["evaluation_steps"] = (
        metric_model.evaluation_steps
        or "1. Analyze the output\n2. Score based on criteria"
    )
    params["reasoning"] = (
        metric_model.reasoning
        or "Consider accuracy, relevance, and completeness"
    )

    # Add score-type specific parameters
    score_type = metric_model.score_type or "numeric"

    if score_type == "numeric":
        # Numeric scores
        if metric_model.min_score is not None:
            params["min_score"] = metric_model.min_score
        if metric_model.max_score is not None:
            params["max_score"] = metric_model.max_score
        if metric_model.threshold is not None:
            params["threshold"] = metric_model.threshold
        if metric_model.threshold_operator:
            params["threshold_operator"] = metric_model.threshold_operator

    elif score_type in ["categorical", "binary"]:
        # Categorical/binary scores
        # SDK requires 'categories' list - create from reference_score if available
        if metric_model.reference_score:
            # Backend stores single reference score, SDK needs categories list
            # Create a minimal categories list with the reference score
            params["categories"] = [metric_model.reference_score, "other"]
            params["passing_categories"] = [metric_model.reference_score]
        else:
            # Default categories for binary or when no reference_score
            if score_type == "binary":
                params["categories"] = ["pass", "fail"]
                params["passing_categories"] = ["pass"]
            else:
                # Categorical without reference - use generic categories
                params["categories"] = ["good", "bad"]
                params["passing_categories"] = ["good"]

    # Add metadata flags
    if metric_model.ground_truth_required is not None:
        params["requires_ground_truth"] = metric_model.ground_truth_required
    if metric_model.context_required is not None:
        params["requires_context"] = metric_model.context_required

    # Add model ID if available (evaluator will handle model lookup)
    if metric_model.model_id:
        params["model_id"] = str(metric_model.model_id)

    logger.debug(f"Built params for metric '{metric_model.name}': {list(params.keys())}")
    return params


def build_metric_params_from_config(metric_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract SDK-compatible parameters from metric configuration dict.

    This handles the existing backend dict-based configs that come from
    create_metric_config_from_model() in metrics_utils.py.

    Args:
        metric_config: Dictionary containing metric configuration

    Returns:
        Dictionary of parameters for SDK metric constructor
    """
    params = {
        "name": metric_config.get("name", "Unnamed Metric"),
        "description": metric_config.get("description"),
    }

    # Extract parameters from nested "parameters" dict if it exists
    config_params = metric_config.get("parameters", {})

    # Add prompt-related fields (all required for RhesisPromptMetric by SDK factory)
    # Provide defaults for metrics that don't have these configured
    metric_name = metric_config.get("name", "Unnamed Metric")
    params["evaluation_prompt"] = config_params.get(
        "evaluation_prompt",
        f"Evaluate the quality of the output for {metric_name}."
    )
    params["evaluation_steps"] = config_params.get(
        "evaluation_steps",
        "1. Analyze the output\n2. Score based on criteria"
    )
    params["reasoning"] = config_params.get(
        "reasoning",
        "Consider accuracy, relevance, and completeness"
    )

    # Add score parameters
    # score_type can be at top level or in parameters
    score_type = metric_config.get("score_type") or config_params.get("score_type", "numeric")

    if score_type == "numeric":
        if "min_score" in config_params:
            params["min_score"] = config_params["min_score"]
        if "max_score" in config_params:
            params["max_score"] = config_params["max_score"]
        if "threshold" in metric_config:
            params["threshold"] = metric_config["threshold"]
        if "threshold_operator" in metric_config:
            params["threshold_operator"] = metric_config["threshold_operator"]

    elif score_type in ["categorical", "binary"]:
        # SDK requires 'categories' list
        # Check if categories are already provided (top level or in parameters)
        categories_found = False
        
        categories_value = metric_config.get("categories") or config_params.get("categories")
        if categories_value and isinstance(categories_value, list) and len(categories_value) >= 2:
            params["categories"] = categories_value
            params["passing_categories"] = (
                metric_config.get("passing_categories") or 
                config_params.get("passing_categories") or 
                categories_value[:1]
            )
            categories_found = True
        elif "reference_score" in metric_config and metric_config.get("reference_score"):
            # Backend stores single reference score, SDK needs categories list
            ref_score = metric_config["reference_score"]
            params["categories"] = [ref_score, "other"]
            params["passing_categories"] = [ref_score]
            categories_found = True
        elif score_type == "binary":
            # Binary type: map to True/False categories (SDK doesn't have binary type)
            # Database migration to add categories field is pending
            params["categories"] = ["True", "False"]
            params["passing_categories"] = ["True"]
            categories_found = True
            logger.info(
                f"Mapped binary metric '{metric_config.get('name', 'unknown')}' to "
                f"categorical with True/False categories"
            )
        
        if not categories_found:
            # Don't default - fail loudly so the metric config can be fixed
            logger.error(
                f"Missing categories for categorical metric '{metric_config.get('name', 'unknown')}'. "
                f"metric_config keys: {list(metric_config.keys())}, "
                f"config_params keys: {list(config_params.keys())}. "
                f"Categorical metrics require 'categories' or 'reference_score' to be set."
            )
            raise ValueError(
                f"Categorical metric '{metric_config.get('name', 'unknown')}' is missing required "
                f"'categories' or 'reference_score' configuration"
            )

    # Add model info if available
    if "model_id" in metric_config and metric_config["model_id"]:
        params["model_id"] = metric_config["model_id"]
    if "model" in config_params:
        params["model"] = config_params["model"]
    if "provider" in config_params:
        params["provider"] = config_params["provider"]

    return params


# ============================================================================
# MAIN ADAPTER FUNCTIONS
# ============================================================================


def create_metric_from_db_model(
    metric_model: MetricModel, organization_id: Optional[str] = None
) -> Optional[BaseMetric]:
    """
    Create an SDK metric instance from a database Metric model.

    This is the main adapter function that handles:
    - Mapping RhesisPromptMetric to appropriate SDK class based on score_type
    - Converting backend types to SDK frameworks
    - Extracting and transforming parameters

    Args:
        metric_model: Database Metric model instance
        organization_id: Optional organization ID for model lookup

    Returns:
        SDK BaseMetric instance, or None if creation fails

    Example:
        >>> metric_model = db.query(Metric).first()
        >>> sdk_metric = create_metric_from_db_model(metric_model)
        >>> result = sdk_metric.evaluate(input_text, output_text, ...)
    """
    try:
        # Validate class name exists
        if not metric_model.class_name:
            logger.warning(
                f"Metric {metric_model.id} is missing class_name, cannot create SDK metric"
            )
            return None

        # Get backend type
        backend_type = (
            metric_model.backend_type.type_value if metric_model.backend_type else "rhesis"
        )

        # Map to SDK framework
        framework = map_backend_type_to_framework(backend_type)

        # Map class name (handles RhesisPromptMetric split)
        sdk_class_name = get_sdk_class_name(metric_model.class_name, metric_model.score_type)

        # Build parameters
        params = build_metric_params_from_model(metric_model, organization_id)

        # Create metric using SDK factory
        logger.info(
            f"Creating SDK metric: framework='{framework}', "
            f"class='{sdk_class_name}', name='{params['name']}'"
        )
        metric = MetricFactory.create(framework, sdk_class_name, **params)

        logger.debug(f"Successfully created SDK metric '{params['name']}'")
        return metric

    except Exception as e:
        logger.error(
            f"Failed to create SDK metric from model {metric_model.id} "
            f"(class={metric_model.class_name}): {e}",
            exc_info=True,
        )
        return None


def create_metric_from_config(
    metric_config: Dict[str, Any], organization_id: Optional[str] = None
) -> Optional[BaseMetric]:
    """
    Create an SDK metric instance from a metric configuration dictionary.

    This handles the dict-based configs that backend currently uses
    (from create_metric_config_from_model in metrics_utils.py).

    Args:
        metric_config: Dictionary containing metric configuration
        organization_id: Optional organization ID for model lookup

    Returns:
        SDK BaseMetric instance, or None if creation fails

    Example:
        >>> config = {
        ...     "class_name": "RhesisPromptMetric",
        ...     "backend": "rhesis",
        ...     "parameters": {"score_type": "numeric", ...}
        ... }
        >>> sdk_metric = create_metric_from_config(config)
    """
    try:
        
        # Validate required fields
        class_name = metric_config.get("class_name")
        if not class_name:
            logger.warning("Metric config missing class_name, cannot create SDK metric")
            return None
        

        backend = metric_config.get("backend", "rhesis")

        # Map to SDK framework
        framework = map_backend_type_to_framework(backend)

        # Get score type from parameters
        score_type = metric_config.get("parameters", {}).get("score_type", "numeric")

        # Map class name (handles RhesisPromptMetric split)
        sdk_class_name = get_sdk_class_name(class_name, score_type)

        # Build parameters
        params = build_metric_params_from_config(metric_config)

        # Create metric using SDK factory
        logger.info(
            f"Creating SDK metric from config: framework='{framework}', "
            f"class='{sdk_class_name}', name='{params['name']}'"
        )
        # Debug: log categories if it's a categorical metric
        if "categories" in params:
            logger.debug(f"🔍 Passing categories to factory: {params['categories']}")
        else:
            logger.warning(f"⚠️ No categories in params! Available params: {list(params.keys())}")
        
        metric = MetricFactory.create(framework, sdk_class_name, **params)

        logger.debug(f"Successfully created SDK metric '{params['name']}'")
        return metric

    except Exception as e:
        logger.error(
            f"❌ [DEBUG ADAPTER] Failed to create SDK metric from config "
            f"(class={metric_config.get('class_name')}): {e}",
            exc_info=True,
        )
        return None


def create_metric(
    metric_source: Union[MetricModel, Dict[str, Any]],
    organization_id: Optional[str] = None,
) -> Optional[BaseMetric]:
    """
    Universal adapter function that accepts either a Metric model or config dict.

    This provides a unified interface for creating SDK metrics from any source.

    Args:
        metric_source: Either a MetricModel instance or a config dictionary
        organization_id: Optional organization ID for model lookup

    Returns:
        SDK BaseMetric instance, or None if creation fails

    Example:
        >>> # From DB model
        >>> metric = create_metric(db.query(Metric).first())
        >>>
        >>> # From config dict
        >>> metric = create_metric({"class_name": "RhesisPromptMetric", ...})
    """
    if isinstance(metric_source, MetricModel):
        return create_metric_from_db_model(metric_source, organization_id)
    elif isinstance(metric_source, dict):
        return create_metric_from_config(metric_source, organization_id)
    else:
        logger.error(
            f"Invalid metric_source type: {type(metric_source)}. Expected MetricModel or dict"
        )
        return None
