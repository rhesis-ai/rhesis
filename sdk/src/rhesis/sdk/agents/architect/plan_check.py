"""Hold the agent's actions against the plan it saved.

The plan is a contract. The LLM writes it, the user approves it, and the
execution phase is meant to carry it out. Two things go wrong with that, and
they need different answers.

A *substitution* is a call whose arguments contradict the plan: a metric
created under a name nobody agreed to, a Multi-Turn set generated as
Single-Turn. The plan and the arguments are both in hand at that moment, so
it is caught before the write lands.

A *shortfall* is a set that ends up smaller than planned. It can only be seen
afterwards, from the count the write reported, so it is recorded as it
happens and rendered into the plan the next prompt shows.

Neither check goes through the LLM. Both compare recorded values in Python
and hand back a finished verdict, so a divergence cannot be talked away --
the lesson of issues #2402 and #2516.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

from rhesis.sdk.agents.architect.plan import ArchitectPlan, MetricSpec
from rhesis.sdk.agents.architect.tool_registry import PlanCategory

# Which argument carries the Single-Turn/Multi-Turn shape. The two test-set
# writers spell it differently.
TEST_TYPE_ARG: Dict[str, str] = {
    "generate_test_set": "test_type",
    "create_test_set_bulk": "test_set_type",
}

_CATEGORY_LABEL: Dict[PlanCategory, str] = {
    PlanCategory.REQUIREMENT: "requirement",
    PlanCategory.METRIC: "metric",
    PlanCategory.TEST_SET: "test set",
}


def _unique(names: Sequence[str]) -> List[str]:
    """De-duplicate case-insensitively, keeping the first spelling and order."""
    seen: set = set()
    out: List[str] = []
    for name in names:
        if not name:
            continue
        key = name.lower()
        if key not in seen:
            seen.add(key)
            out.append(name)
    return out


def planned_names(plan: ArchitectPlan, category: PlanCategory) -> List[str]:
    """Every name the plan offers for a category.

    A requirement or metric can be named in a mapping, or in a test set's
    requirement list, without having a spec entry of its own -- the plan
    validator does not require one. Creating it is then squarely in line with
    the plan, so collecting from everywhere the plan mentions a name keeps the
    guard off legitimate work.
    """
    if category == PlanCategory.REQUIREMENT:
        names = [spec.name for spec in plan.requirements]
        names += [mapping.requirement for mapping in plan.requirement_metric_mappings]
        for test_set in plan.test_sets:
            names += test_set.requirements
        return _unique(names)

    if category == PlanCategory.METRIC:
        names = [spec.name for spec in plan.metrics]
        for mapping in plan.requirement_metric_mappings:
            names += mapping.metrics
        return _unique(names)

    if category == PlanCategory.TEST_SET:
        return _unique([spec.name for spec in plan.test_sets])

    return []


def find_by_name(items: Sequence[Any], name: Any) -> Optional[Any]:
    """The spec with this name, matched case-insensitively."""
    if not isinstance(name, str) or not name:
        return None
    for item in items:
        if item.name.lower() == name.lower():
            return item
    return None


def check_name(plan: ArchitectPlan, category: PlanCategory, name: Any) -> Optional[str]:
    """Reject a create call for something the plan never mentions."""
    label = _CATEGORY_LABEL.get(category)
    if label is None or not isinstance(name, str) or not name:
        return None

    candidates = planned_names(plan, category)
    if any(candidate.lower() == name.lower() for candidate in candidates):
        return None

    listed = ", ".join(f"'{candidate}'" for candidate in candidates) if candidates else "none"
    return (
        f"{label.capitalize()} name '{name}' does not match anything in the "
        f"saved plan. Planned {label}s: {listed}. Use the planned name. If "
        f"the user has genuinely asked for something new, call save_plan "
        f"first so the plan and the work stay the same thing."
    )


def check_test_set_shape(
    plan: ArchitectPlan, tool_name: str, arguments: Dict[str, Any]
) -> Optional[str]:
    """Reject a test set being built in a shape the plan did not call for."""
    argument = TEST_TYPE_ARG.get(tool_name)
    if argument is None or argument not in arguments:
        return None

    spec = find_by_name(plan.test_sets, arguments.get("name"))
    if spec is None:
        return None

    sent = arguments[argument]
    if not isinstance(sent, str) or sent == spec.test_type:
        return None

    return (
        f"Test set '{spec.name}' is planned as {spec.test_type} but this call "
        f"sends {argument}='{sent}'. A metric only runs against the test type "
        f"in its scope, so a set built in the other shape is evaluated by "
        f"nothing. Send '{spec.test_type}', or call save_plan first."
    )


def _check_scope(spec: MetricSpec, arguments: Dict[str, Any]) -> Optional[str]:
    if "metric_scope" not in arguments:
        return None
    sent = arguments["metric_scope"]
    # An empty or malformed scope is the server's to reject, not ours.
    if not isinstance(sent, list) or not sent:
        return None
    if {str(entry) for entry in sent} == set(spec.metric_scope):
        return None
    return (
        f"Metric '{spec.name}' is planned with metric_scope "
        f"{list(spec.metric_scope)} but this call sends {sent}. The scope "
        f"decides which tests the metric runs against, so a wrong one means "
        f"it silently never runs. Send the planned scope, or call save_plan."
    )


def _check_threshold(spec: MetricSpec, arguments: Dict[str, Any]) -> Optional[str]:
    if "threshold" not in arguments:
        return None
    sent = arguments["threshold"]
    if isinstance(sent, bool) or not isinstance(sent, (int, float)):
        return None
    if math.isclose(float(sent), float(spec.threshold), rel_tol=1e-9, abs_tol=1e-9):
        return None
    return (
        f"Metric '{spec.name}' is planned with threshold {spec.threshold} but "
        f"this call sends {sent}. That is the line between pass and fail. "
        f"Send the planned threshold, or call save_plan first."
    )


def _check_threshold_operator(spec: MetricSpec, arguments: Dict[str, Any]) -> Optional[str]:
    if "threshold_operator" not in arguments:
        return None
    sent = arguments["threshold_operator"]
    if not isinstance(sent, str) or sent == spec.threshold_operator:
        return None
    return (
        f"Metric '{spec.name}' is planned with threshold_operator "
        f"'{spec.threshold_operator}' but this call sends '{sent}'. That "
        f"reverses which side of the threshold passes. Send the planned "
        f"operator, or call save_plan first."
    )


def check_metric_shape(plan: ArchitectPlan, arguments: Dict[str, Any]) -> Optional[str]:
    """Reject a metric whose scoring differs from the planned one.

    Only fields the call actually carries are compared. A plan field left at
    its default says nothing about a call that omits it, and treating that as
    a mismatch would fire on ordinary work until nobody read the warnings.
    """
    spec = find_by_name(plan.metrics, arguments.get("name"))
    if spec is None:
        return None

    for problem in (
        _check_scope(spec, arguments),
        _check_threshold(spec, arguments),
        _check_threshold_operator(spec, arguments),
    ):
        if problem:
            return problem
    return None


def tests_written(data: Any) -> Optional[int]:
    """How many tests a bulk write reported creating.

    Both bulk writers answer in ``total_tests``. Anything else -- an error
    body, a shape change -- reads as "unknown" rather than as zero, because
    recording a zero would invent a shortfall that did not happen.
    """
    if not isinstance(data, dict):
        return None
    value = data.get("total_tests")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def apply_observed_counts(plan: ArchitectPlan, observed: Dict[str, int]) -> None:
    """Copy the counts seen this session onto the matching plan specs.

    ``actual_tests`` is internal, so ``save_plan`` strips it and the LLM's
    payload restores the default. The counts are kept outside the plan and
    written back here, the same way ``completed`` is recovered by
    ``_reconcile_plan_with_session_evidence``.
    """
    for spec in plan.test_sets:
        count = observed.get(spec.name.lower())
        if count is not None:
            spec.actual_tests = count


def shortfall_lines(plan: ArchitectPlan) -> List[str]:
    """One line per test set that came up short, for the progress summary."""
    lines: List[str] = []
    for spec in plan.test_sets:
        missing = spec.shortfall()
        if missing is not None:
            lines.append(f"'{spec.name}' has {spec.actual_tests} of {spec.num_tests} planned tests")
    return lines


__all__ = [
    "TEST_TYPE_ARG",
    "apply_observed_counts",
    "check_metric_shape",
    "check_name",
    "check_test_set_shape",
    "find_by_name",
    "planned_names",
    "shortfall_lines",
    "tests_written",
]
