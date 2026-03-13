import dataclasses
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.models.metric import Metric as MetricModel
from rhesis.backend.metrics.result_builder import MetricResultBuilder
from rhesis.backend.metrics.utils import diagnose_invalid_metric
from rhesis.sdk.metrics import BaseMetric, MetricConfig
from rhesis.sdk.metrics.base import ScoreType
from rhesis.sdk.metrics.utils import backend_config_to_sdk_config

logger = logging.getLogger(__name__)


def metric_model_to_config(metric: MetricModel) -> MetricConfig:
    """Convert a Metric database model to a MetricConfig."""
    common_fields = [
        "name",
        "class_name",
        "description",
        "evaluation_prompt",
        "evaluation_steps",
        "reasoning",
        "evaluation_examples",
        "score_type",
        "ground_truth_required",
        "context_required",
    ]
    config = {field: getattr(metric, field, None) for field in common_fields}
    config["backend"] = metric.backend_type.type_value if metric.backend_type else "rhesis"
    config["name"] = config["name"] or f"Metric_{metric.id}"
    config["description"] = config["description"] or f"Metric evaluation for {metric.class_name}"
    config["score_type"] = config["score_type"] or ScoreType.NUMERIC.value

    score_type = metric.score_type or ScoreType.NUMERIC.value
    if score_type == ScoreType.CATEGORICAL.value:
        config["categories"] = metric.categories
        config["passing_categories"] = metric.passing_categories
    else:
        config["threshold"] = metric.threshold if metric.threshold is not None else 0.5
        config["threshold_operator"] = metric.threshold_operator
        if metric.min_score is not None:
            config["min_score"] = metric.min_score
        if metric.max_score is not None:
            config["max_score"] = metric.max_score

    config = backend_config_to_sdk_config(config)
    field_names = {f.name for f in dataclasses.fields(MetricConfig)}
    filtered = {k: v for k, v in config.items() if k in field_names}
    cfg = MetricConfig(**filtered)
    if model_id := (str(metric.model_id) if metric.model_id else None):
        cfg.parameters = dict(cfg.parameters or {})
        cfg.parameters["model_id"] = model_id
    if metric.model and metric.model.provider_type:
        cfg.parameters = dict(cfg.parameters or {})
        cfg.parameters["provider"] = metric.model.provider_type.type_value
        cfg.parameters["model"] = metric.model.model_name
    return cfg


def dict_to_metric_config(config: Dict[str, Any]) -> MetricConfig:
    """Convert a dict to MetricConfig, flattening nested 'parameters' into top-level."""
    params = config.get("parameters") or {}
    if not isinstance(params, dict):
        params = {}
    merged = {**config, **params}
    params = dict(params)
    for key in ("model_id", "provider", "model"):
        if key in merged:
            params[key] = merged[key]
    merged["parameters"] = params
    field_names = {f.name for f in dataclasses.fields(MetricConfig)}
    filtered = {k: v for k, v in merged.items() if k in field_names}
    return MetricConfig(**filtered)


def normalize_config(
    config: Union[Dict[str, Any], MetricConfig, MetricModel],
) -> MetricConfig:
    """Normalize any supported config type to MetricConfig."""
    if isinstance(config, MetricConfig):
        return config
    if isinstance(config, MetricModel):
        return metric_model_to_config(config)
    if isinstance(config, dict):
        return dict_to_metric_config(config)
    raise TypeError(f"Unsupported config type: {type(config).__name__}")


def validate_metric_configs(
    metrics: List[Union[Dict[str, Any], MetricConfig, MetricModel]],
) -> Tuple[List[MetricConfig], Dict[str, Any]]:
    """Normalize and validate raw metric configs.

    Returns:
        Tuple of (valid MetricConfig list, dict of invalid metric error results).
    """
    metric_configs: List[MetricConfig] = []
    invalid_metric_results: Dict[str, Any] = {}

    for i, raw_config in enumerate(metrics):
        try:
            config = normalize_config(raw_config)
        except TypeError:
            invalid_key = f"InvalidMetric_{i}"
            type_name = type(raw_config).__name__
            invalid_metric_results[invalid_key] = MetricResultBuilder.error(
                reason=f"Invalid config type: {type_name}",
                backend="unknown",
                name=invalid_key,
                class_name="Unknown",
                description=f"Invalid config type: {type_name}",
                error=f"Invalid config type: {type_name}",
                threshold=0.0,
            )
            logger.warning(f"Invalid config type for metric {i}: {type_name}")
            continue

        error_reason = diagnose_invalid_metric(config)
        if error_reason and error_reason != "unknown validation error":
            invalid_key = f"InvalidMetric_{i}"
            backend_str = getattr(config.backend, "value", config.backend) or "unknown"
            invalid_metric_results[invalid_key] = MetricResultBuilder.error(
                reason=f"Invalid metric configuration: {error_reason}",
                backend=backend_str,
                name=config.name or invalid_key,
                class_name=config.class_name or "Unknown",
                description=f"Failed to load metric: {error_reason}",
                error=error_reason,
                threshold=0.0,
            )
            logger.warning(f"Invalid metric configuration {i}: {error_reason}")
        else:
            metric_configs.append(config)

    if invalid_metric_results:
        logger.warning(
            f"Found {len(invalid_metric_results)} invalid metrics that will be reported as errors"
        )

    logger.debug(
        f"Using {len(metric_configs)} valid metrics and "
        f"{len(invalid_metric_results)} invalid metrics"
    )

    return metric_configs, invalid_metric_results


def _resolve_metric_model(
    model_id: str,
    db: Session,
    organization_id: Optional[str],
    metric_name_for_log: str,
) -> Optional[Any]:
    """Fetch a metric-specific LLM model from the database and instantiate it."""
    try:
        from rhesis.backend.app import crud
        from rhesis.sdk.models.factory import get_model

        model_record = crud.get_model(
            db,
            UUID(model_id) if isinstance(model_id, str) else model_id,
            organization_id,
        )

        if model_record and model_record.provider_type:
            llm = get_model(
                provider=model_record.provider_type.type_value,
                model_name=model_record.model_name,
                api_key=model_record.key,
            )
            logger.info(
                f"[METRIC_MODEL] Using metric-specific model for "
                f"'{metric_name_for_log}': {model_record.name} "
                f"(provider={model_record.provider_type.type_value}, "
                f"model={model_record.model_name})"
            )
            return llm

        logger.warning(
            f"[METRIC_MODEL] Model ID {model_id} not found for metric '{metric_name_for_log}'"
        )
    except Exception as e:
        logger.warning(
            f"[METRIC_MODEL] Error fetching metric-specific model for '{metric_name_for_log}': {e}"
        )
    return None


def prepare_metrics(
    metrics: List[MetricConfig],
    expected_output: Optional[str],
    context: Optional[List[str]] = None,
    model: Optional[Any] = None,
    db: Optional[Session] = None,
    organization_id: Optional[str] = None,
) -> List[Tuple[str, BaseMetric, MetricConfig, str]]:
    """Instantiate metric objects via SDK factory, resolving models from DB.

    Args:
        metrics: List of metric configurations (may contain None values).
        expected_output: The expected output (to check if ground truth is required).
        context: List of context strings (to check if context is required).
        model: Optional default LLM model for metrics evaluation.
        db: Optional database session for fetching metric-specific models.
        organization_id: Optional organization ID for secure model lookups.

    Returns:
        List of tuples containing (class_name, metric_instance, metric_config, backend).
    """
    logger.info(f"Preparing {len(metrics)} metrics for evaluation")
    metric_tasks: List[Tuple[str, BaseMetric, MetricConfig, str]] = []

    for metric_config in metrics:
        class_name = metric_config.class_name
        backend = getattr(metric_config.backend, "value", metric_config.backend)
        threshold = metric_config.threshold
        parameters = metric_config.parameters or {}
        model_id = parameters.get("model_id")

        try:
            metric_params: Dict[str, Any] = {"threshold": threshold, **parameters}
            metric_name_for_log = metric_config.name or class_name

            # Determine which model to use for this metric
            # Priority: metric-specific model > user's default model > system default
            metric_model = None

            if model_id and db:
                metric_model = _resolve_metric_model(
                    model_id, db, organization_id, metric_name_for_log
                )

            if metric_model is None and model is not None:
                metric_model = model
                logger.debug(
                    f"[METRIC_MODEL] Using user's default model for '{metric_name_for_log}'"
                )

            if metric_model is not None:
                metric_params["model"] = metric_model

            from rhesis.sdk.metrics import MetricFactory

            metric_name = metric_config.name or class_name
            logger.debug(
                f"[SDK_DIRECT] Creating metric directly via SDK: {metric_name or class_name}"
            )

            config_dict = dataclasses.asdict(metric_config)
            if metric_params:
                if config_dict.get("parameters") is None:
                    config_dict["parameters"] = {}
                config_dict["parameters"].update(metric_params)

            params_dict = config_dict.get("parameters", {})
            factory_params = {**config_dict}
            factory_params.update(params_dict)

            factory_params.pop("class_name", None)
            factory_params.pop("backend", None)
            factory_params.pop("parameters", None)

            try:
                metric = MetricFactory.create(backend, class_name, **factory_params)
            except Exception as create_error:
                logger.error(
                    f"[SDK_DIRECT] Failed to create metric "
                    f"'{metric_name or class_name}' "
                    f"(class: {class_name}, backend: {backend}): "
                    f"{create_error}",
                    exc_info=True,
                )
                continue

            if metric.requires_ground_truth and expected_output is None:
                logger.debug(
                    f"Skipping metric '{class_name}' as it requires "
                    f"ground truth which is not provided"
                )
                continue

            metric_tasks.append((class_name, metric, metric_config, backend))

        except Exception as e:
            metric_name = metric_config.name or class_name
            error_msg = (
                f"Error preparing metric '{metric_name or class_name}' "
                f"(class: '{class_name}', backend: '{backend}'): {str(e)}"
            )
            logger.error(error_msg, exc_info=True)

    return metric_tasks
