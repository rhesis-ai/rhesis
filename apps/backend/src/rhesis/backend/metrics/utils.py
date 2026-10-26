from rhesis.sdk.metrics import MetricConfig


def diagnose_invalid_metric(config: MetricConfig) -> str:
    """
    Diagnose the reason why a metric configuration is invalid.

    Args:
        config: The metric configuration (must be MetricConfig; normalize before calling).

    Returns:
        A string describing the reason why the metric configuration is invalid
    """
    if config is None:
        return "configuration is None"

    missing_fields = []
    if not config.class_name or (
        isinstance(config.class_name, str) and not config.class_name.strip()
    ):
        missing_fields.append("class_name")
    backend_val = getattr(config.backend, "value", config.backend)
    if not backend_val or (isinstance(backend_val, str) and not backend_val.strip()):
        missing_fields.append("backend")
    if missing_fields:
        return f"missing or empty required fields: {', '.join(missing_fields)}"

    return "unknown validation error"
