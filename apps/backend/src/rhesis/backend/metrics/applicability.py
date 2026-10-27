"""Which metrics apply to a test, by the expectations the test carries.

A metric that compares with an expectation the test doesn't have (a trajectory metric on a
test without expected tool calls) is not applicable to it: it is left out, the way a metric
scoped to the other test type is, rather than scored or failed.
"""

import logging
from typing import Any, List, Optional

from sqlalchemy import inspect as sa_inspect

from rhesis.backend.app.models.metric import Metric as MetricModel
from rhesis.backend.app.schemas.multi_turn_test_config import EXPECTED_TOOL_CALLS_KEY
from rhesis.sdk.metrics import BaseMetric, Expectations

logger = logging.getLogger(__name__)

_NATIVE_BACKENDS = ("rhesis", "custom")


def expected_tool_calls(test_configuration: Any) -> Optional[List[dict]]:
    """A test's expected tool calls, or None when the test doesn't say."""
    if not isinstance(test_configuration, dict):
        return None
    return test_configuration.get(EXPECTED_TOOL_CALLS_KEY)


def _backend_and_class(metric: Any) -> tuple:
    """The metric's backend, or None when a Metric row hasn't loaded it (rows are often read
    with lazy loads refused), and its class name."""
    if isinstance(metric, dict):
        return metric.get("backend") or metric.get("backend_type"), metric.get("class_name")
    class_name = getattr(metric, "class_name", None)
    if isinstance(metric, MetricModel):
        if "backend_type" in sa_inspect(metric).unloaded:
            return None, class_name
        return (metric.backend_type.type_value if metric.backend_type else "rhesis"), class_name
    backend = getattr(metric, "backend", None)
    return getattr(backend, "value", backend), class_name


def metric_class(metric: Any) -> Optional[type[BaseMetric]]:
    """The SDK class a Metric row, MetricConfig or config dict builds, when it is a native one.

    A row whose backend isn't loaded is matched by class name, which native classes don't
    share with other backends'.
    """
    backend, class_name = _backend_and_class(metric)
    if (backend is not None and backend not in _NATIVE_BACKENDS) or not class_name:
        return None
    from rhesis.sdk.metrics.providers.native.factory import RhesisMetricFactory

    factory = RhesisMetricFactory()
    if class_name not in factory.list_supported_metrics():
        return None
    return factory.metric_class(class_name)


def needs_model(metric: Any) -> bool:
    cls = metric_class(metric)
    return getattr(cls, "REQUIRES_MODEL", True)


def applies(metric: Any, expectations: Optional[Expectations]) -> bool:
    """Whether the test's expectations hold every field the metric compares with."""
    cls = metric_class(metric)
    required = getattr(cls, "REQUIRED_EXPECTATIONS", ())
    return all(getattr(expectations, field, None) is not None for field in required)


def applicable(metrics: List[Any], expectations: Optional[Expectations]) -> List[Any]:
    """The metrics that apply to a test with these expectations."""
    kept, skipped = [], []
    for metric in metrics:
        (kept if applies(metric, expectations) else skipped).append(metric)
    if skipped:
        names = [getattr(m, "name", None) or "?" for m in skipped]
        logger.debug(f"Not applicable, the test lacks what they compare with: {names}")
    return kept
