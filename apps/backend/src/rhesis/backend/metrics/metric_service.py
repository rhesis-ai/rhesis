import dataclasses
from typing import Any, Dict, Union

from rhesis.backend.app.models.metric import Metric as MetricModel
from rhesis.sdk.metrics import MetricConfig
from rhesis.sdk.metrics.base import ScoreType
from rhesis.sdk.metrics.utils import backend_config_to_sdk_config


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
    config["backend"] = (
        metric.backend_type.type_value if metric.backend_type else "rhesis"
    )
    config["name"] = config["name"] or f"Metric_{metric.id}"
    config["description"] = (
        config["description"] or f"Metric evaluation for {metric.class_name}"
    )
    config["score_type"] = config["score_type"] or ScoreType.NUMERIC.value

    score_type = metric.score_type or ScoreType.NUMERIC.value
    if score_type == ScoreType.CATEGORICAL.value:
        config["categories"] = metric.categories
        config["passing_categories"] = metric.passing_categories
    else:
        config["threshold"] = (
            metric.threshold if metric.threshold is not None else 0.5
        )
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
