"""Which metrics apply to a test, by their target and the expectations the test carries.

A metric that can't judge a test is not applicable to it: it is left out rather than scored
or failed. That is a metric judging the conversation on a single-turn test, a metric
comparing with a reference answer on a conversation (which has none), and a metric
comparing with an expectation the test doesn't have (a trajectory metric on a test without
expected tool calls).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, List, Optional

from sqlalchemy import inspect as sa_inspect

from rhesis.backend.app.models.metric import Metric as MetricModel
from rhesis.backend.app.schemas.multi_turn_test_config import EXPECTED_TOOL_CALLS_KEY

# Imported by run_models, which core installs load without the SDK.
if TYPE_CHECKING:
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
    try:
        from rhesis.sdk.metrics.providers.native.factory import RhesisMetricFactory
    except ImportError:  # a core install, which runs no native metric
        return None

    factory = RhesisMetricFactory()
    if class_name not in factory.list_supported_metrics():
        return None
    return factory.metric_class(class_name)


def needs_model(metric: Any) -> bool:
    cls = metric_class(metric)
    return getattr(cls, "REQUIRES_MODEL", True)


def _stored_target(metric: Any) -> Any:
    if isinstance(metric, dict):
        return metric.get("target") or (metric.get("config") or {}).get("target")
    if isinstance(metric, MetricModel):
        if "config" in sa_inspect(metric).unloaded:
            return None
        return (metric.config or {}).get("target")
    return getattr(metric, "target", None)


def metric_target(metric: Any) -> Optional[str]:
    """What the metric judges (``"turn"``, ``"conversation"``, ...): its own target, else its
    class's default; None when neither is known."""
    target = _stored_target(metric)
    if isinstance(target, dict):
        target = target.get("on")
    target = getattr(target, "value", target)
    if isinstance(target, str) and target:
        return target
    cls = _builtin_class(metric)
    if cls is None:
        return None
    from rhesis.sdk.metrics.targets import default_target

    default = default_target(cls)
    return default.value if default is not None else None


def _builtin_class(metric: Any) -> Any:
    """The native or DeepEval class a metric is built from, or None."""
    _, class_name = _backend_and_class(metric)
    if not isinstance(class_name, str):
        return None
    try:
        from rhesis.backend.app.schemas.metric import builtin_metric_class

        return builtin_metric_class(class_name)
    except ImportError:  # a core install, which runs no metric
        return None


def _compares_with_response(metric: Any) -> bool:
    cls = _builtin_class(metric)
    if "response" in getattr(cls, "REQUIRED_EXPECTATIONS", ()):
        return True
    # A class can compare with one whatever its row says (DeepEval's contextual recall).
    if getattr(cls, "requires_ground_truth", False) is True:
        return True
    if isinstance(metric, dict):
        return bool(metric.get("ground_truth_required") or metric.get("requires_ground_truth"))
    if isinstance(metric, MetricModel):
        return bool(metric.ground_truth_required)
    return getattr(metric, "requires_ground_truth", False) is True


def fits(metric: Any, conversation: bool) -> bool:
    """Whether the metric can judge a conversation (``conversation``) or a single turn,
    whatever the test expects."""
    if conversation:
        # A conversation has no expected response to compare with.
        return not _compares_with_response(metric)
    return metric_target(metric) != "conversation"


def applies(metric: Any, expectations: Optional[Expectations], conversation: bool = False) -> bool:
    """Whether the metric can judge a test with these expectations; ``conversation`` says
    whether the test is one."""
    required = getattr(metric_class(metric), "REQUIRED_EXPECTATIONS", ())
    if not all(getattr(expectations, field, None) is not None for field in required):
        return False
    return fits(metric, conversation)


def applicable(
    metrics: List[Any], expectations: Optional[Expectations], conversation: bool = False
) -> List[Any]:
    """The metrics that apply to a test with these expectations."""
    kept, skipped = [], []
    for metric in metrics:
        (kept if applies(metric, expectations, conversation) else skipped).append(metric)
    if skipped:
        names = [getattr(m, "name", None) or "?" for m in skipped]
        kind = "conversation" if conversation else "single-turn test"
        logger.debug(f"Not applicable to this {kind}: {names}")
    return kept
