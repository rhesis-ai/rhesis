"""
Simplified adapter for creating SDK metrics from database models.

After database migration, the adapter no longer needs complex mapping logic:
- Database stores SDK class names directly (NumericJudge, CategoricalJudge)
- Database stores categories as JSONB
- No more "RhesisPromptMetric" or "binary" score types

This module now provides simple conversion from database models to SDK metric instances.
"""

from typing import Any, Dict, Optional, Union

from rhesis.backend.app.models.metric import Metric as MetricModel
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.sdk.metrics import BaseMetric, MetricFactory

# Backend type to SDK framework mapping
BACKEND_TO_FRAMEWORK_MAP = {
    "rhesis": "rhesis",
    "deepeval": "deepeval",
    "ragas": "ragas",
    "custom": "rhesis",
    "custom-code": "rhesis",
    "custom-prompt": "rhesis",
    "framework": "deepeval",  # Legacy fallback
}


def map_backend_type_to_framework(backend_type: Optional[str]) -> str:
    """
    Map backend type to SDK framework name.

    Args:
        backend_type: Backend type from database (e.g., "rhesis", "deepeval")

    Returns:
        SDK framework name
    """
    if not backend_type:
        return "rhesis"

    return BACKEND_TO_FRAMEWORK_MAP.get(backend_type, backend_type)


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
        "evaluation_prompt": metric_model.evaluation_prompt,
        "evaluation_steps": metric_model.evaluation_steps,
        "reasoning": metric_model.reasoning,
        "evaluation_examples": metric_model.evaluation_examples,
    }

    # Add score-type specific parameters
    if metric_model.score_type == "numeric":
        if metric_model.min_score is not None:
            params["min_score"] = metric_model.min_score
        if metric_model.max_score is not None:
            params["max_score"] = metric_model.max_score
        if metric_model.threshold is not None:
            params["threshold"] = metric_model.threshold
        if metric_model.threshold_operator:
            params["threshold_operator"] = metric_model.threshold_operator

    elif metric_model.score_type == "categorical":
        # Categories are already stored in the database
        if metric_model.categories:
            params["categories"] = metric_model.categories
        if metric_model.passing_categories:
            params["passing_categories"] = metric_model.passing_categories

    # Add metadata flags
    if metric_model.ground_truth_required is not None:
        params["requires_ground_truth"] = metric_model.ground_truth_required
    if metric_model.context_required is not None:
        params["requires_context"] = metric_model.context_required

    # Add model ID if available
    if metric_model.model_id:
        params["model_id"] = str(metric_model.model_id)

    return params


def build_metric_params_from_config(metric_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract SDK-compatible parameters from metric configuration dict.

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

    # Add prompt-related fields
    params["evaluation_prompt"] = config_params.get(
        "evaluation_prompt", metric_config.get("evaluation_prompt", "")
    )
    params["evaluation_steps"] = config_params.get(
        "evaluation_steps", metric_config.get("evaluation_steps")
    )
    params["reasoning"] = config_params.get("reasoning", metric_config.get("reasoning"))
    params["evaluation_examples"] = config_params.get(
        "evaluation_examples", metric_config.get("evaluation_examples")
    )

    # Add score parameters
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

    elif score_type == "categorical":
        # Categories should already be in the config
        categories_value = metric_config.get("categories") or config_params.get("categories")
        if categories_value and isinstance(categories_value, list):
            params["categories"] = categories_value
            params["passing_categories"] = (
                metric_config.get("passing_categories")
                or config_params.get("passing_categories")
                or categories_value[:1]  # Default to first category
            )
        else:
            raise ValueError(
                f"Categorical metric '{metric_config.get('name', 'unknown')}' is missing "
                f"required 'categories' field"
            )

    # Add model info if available
    if "model_id" in metric_config and metric_config["model_id"]:
        params["model_id"] = metric_config["model_id"]
    if "model" in config_params:
        params["model"] = config_params["model"]
    if "provider" in config_params:
        params["provider"] = config_params["provider"]

    return params


def create_metric_from_db_model(
    metric_model: MetricModel, organization_id: Optional[str] = None
) -> Optional[BaseMetric]:
    """
    Create an SDK metric instance from a database Metric model.

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
        if not metric_model.class_name:
            logger.warning(
                f"Metric {metric_model.id} is missing class_name, cannot create SDK metric"
            )
            return None

        # Get backend type and map to framework
        backend_type = (
            metric_model.backend_type.type_value if metric_model.backend_type else "rhesis"
        )
        framework = map_backend_type_to_framework(backend_type)

        # Build parameters from database model
        params = build_metric_params_from_model(metric_model, organization_id)

        # Create metric using SDK factory
        # Database now stores SDK-compatible class names directly (no mapping needed)
        logger.info(
            f"Creating SDK metric: framework='{framework}', "
            f"class='{metric_model.class_name}', name='{params['name']}'"
        )
        metric = MetricFactory.create(framework, metric_model.class_name, **params)

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

    Args:
        metric_config: Dictionary containing metric configuration
        organization_id: Optional organization ID for model lookup

    Returns:
        SDK BaseMetric instance, or None if creation fails

    Example:
        >>> config = {
        ...     "class_name": "NumericJudge",
        ...     "backend": "rhesis",
        ...     "parameters": {"score_type": "numeric", ...}
        ... }
        >>> sdk_metric = create_metric_from_config(config)
    """
    try:
        class_name = metric_config.get("class_name")
        if not class_name:
            logger.warning("Metric config missing class_name, cannot create SDK metric")
            return None

        backend = metric_config.get("backend", "rhesis")
        framework = map_backend_type_to_framework(backend)

        # Build parameters from config
        params = build_metric_params_from_config(metric_config)

        # Create metric using SDK factory
        logger.info(
            f"Creating SDK metric from config: framework='{framework}', "
            f"class='{class_name}', name='{params['name']}'"
        )
        metric = MetricFactory.create(framework, class_name, **params)

        logger.debug(f"Successfully created SDK metric '{params['name']}'")
        return metric

    except Exception as e:
        logger.error(
            f"Failed to create SDK metric from config "
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
        >>> metric = create_metric({"class_name": "NumericJudge", ...})
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
