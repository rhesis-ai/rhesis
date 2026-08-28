"""Snapshot which metrics apply to which tests, frozen at dispatch time.

Stored on ``test_run.attributes["metric_plan"]`` so the verdict grid's frame
(requirements, metric rows, column count) is known before any test runs --
before this, the grid could only be built retroactively from recorded
``test_result`` rows, which is what ``app/services/test_run.py`` falls back
to for a run dispatched before this shipped.

Lives under ``jobs/`` rather than ``app/services/`` because it needs
``get_test_metrics`` and ``filter_configs_by_scope``, both jobs-internal --
see ``apps/backend/AGENTS.md``'s "jobs/ depends on services/utils, never the
reverse" rule.

Plan shape::

    {
      "source": "requirement" | "test_set" | "execution_time" | "none" | "mixed",
      "requirements": [
        {"id", "name", "metrics": [{"key", "name", "id", "ambiguous"}], "test_ids": [...]}
      ],
      "test_order": [test_id, ...],          # every column, in grid order
      "cell_keys": {test_id: {metric_ref: jsonb_key}},
    }

``test_ids`` is what scopes a metric row to its own requirement's columns: a
row spans every column in ``test_order``, so without it a row would claim
cells for tests belonging to some other requirement, and (when two
requirements carry a same-named metric) read that other requirement's
verdicts as its own.

``cell_keys`` maps a metric row to the ``test_metrics`` JSONB key the runtime
will actually store that metric's result under, per test. It is not always
the row's own ``key``: the runtime assigns duplicate-name suffixes *after*
scope filtering (``batch/evaluation.py`` filters, then
``LocalStrategy._generate_unique_metric_keys`` numbers the survivors), so for
two same-named metrics of differing scope the survivor takes the bare name
whichever one it is. A missing entry means the metric does not apply to that
test at all.
"""

import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud.test_run import get_ordered_tests_for_test_set
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.app.schemas.metric import MetricScope
from rhesis.backend.jobs.execution.evaluation import filter_configs_by_scope
from rhesis.backend.jobs.execution.executors.data import get_test_metrics

_EMPTY_PLAN: Dict[str, Any] = {
    "source": "none",
    "requirements": [],
    "test_order": [],
    "cell_keys": {},
}


def _assign_metric_keys(metrics: List[models.Metric]) -> List[Tuple[str, models.Metric, bool]]:
    """Mirror ``_generate_unique_metric_keys`` in metrics/strategies/local.py.

    Same stable sort (name, class_name, id) and ``_N`` suffixing, so a
    metric's key here matches the key its result actually lands under.
    ``ambiguous`` is True whenever more than one metric in this group shares
    a base key, including the one that keeps the bare key.
    """
    base_keys = [m.name if m.name and m.name.strip() else m.class_name for m in metrics]
    counts: Dict[str, int] = {}
    for key in base_keys:
        counts[key] = counts.get(key, 0) + 1

    order = sorted(
        range(len(metrics)),
        key=lambda i: (base_keys[i], metrics[i].class_name or "", str(metrics[i].id or "")),
    )
    used: set = set()
    assigned: Dict[int, str] = {}
    for i in order:
        base_key = base_keys[i]
        unique_key = base_key
        counter = 1
        while unique_key in used:
            unique_key = f"{base_key}_{counter}"
            counter += 1
        used.add(unique_key)
        assigned[i] = unique_key

    return [(assigned[i], metrics[i], counts[base_keys[i]] > 1) for i in range(len(metrics))]


def _metric_ref(metric: models.Metric, key: str) -> str:
    """Stable per-row identity for cell_keys, independent of the display key."""
    return str(metric.id) if metric.id else key


def _requirement_names(
    db: Session, requirement_ids: List[str], organization_id: Optional[str]
) -> Dict[str, str]:
    if not requirement_ids:
        return {}
    query = db.query(models.Requirement.id, models.Requirement.name).filter(
        models.Requirement.id.in_([uuid.UUID(r) for r in requirement_ids])
    )
    if organization_id:
        query = query.filter(models.Requirement.organization_id == uuid.UUID(str(organization_id)))
    return {str(rid): name for rid, name in query.all()}


def build_metric_plan(
    db: Session,
    test_config: TestConfiguration,
    test_set: TestSet,
    organization_id: str = None,
    user_id: str = None,
) -> Dict[str, Any]:
    """Snapshot which metrics apply to which tests, frozen at dispatch.

    Metric resolution is delegated to ``get_test_metrics`` per requirement
    group rather than once for the whole run: its three-level priority
    (execution-time config > test set > requirement) is evaluated against a
    specific test, so asking one arbitrary "sample" test would let a single
    requirement-less test collapse the entire plan to zero rows.

    Restores ``db.info['_scope']`` on the way out. ``get_test_metrics`` calls
    ``bind_scope_to_session``, and this runs inside the FastAPI request that
    dispatches the run -- leaving that bound would apply a stale project
    filter to every later query on the request's session (see
    ``apps/backend/AGENTS.md``, "Side-channel and in-request scope binding").
    """
    scope_before = db.info.get("_scope")
    try:
        return _build_metric_plan(db, test_config, test_set, organization_id, user_id)
    finally:
        if scope_before is None:
            db.info.pop("_scope", None)
        else:
            db.info["_scope"] = scope_before


def _build_metric_plan(
    db: Session,
    test_config: TestConfiguration,
    test_set: TestSet,
    organization_id: Optional[str],
    user_id: Optional[str],
) -> Dict[str, Any]:
    ordered = get_ordered_tests_for_test_set(db, test_set.id, organization_id)
    test_order = [test_id for test_id, _, _ in ordered]
    if not ordered:
        return {**_EMPTY_PLAN, "test_order": test_order}

    tests_by_group: Dict[Optional[str], List[str]] = {}
    is_multi_turn_by_test: Dict[str, bool] = {}
    for test_id, req_id, is_multi_turn in ordered:
        tests_by_group.setdefault(req_id, []).append(test_id)
        is_multi_turn_by_test[test_id] = is_multi_turn

    requirement_ids = sorted(g for g in tests_by_group if g is not None)
    groups: List[Optional[str]] = requirement_ids + ([None] if None in tests_by_group else [])
    requirement_names = _requirement_names(db, requirement_ids, organization_id)

    requirements_payload: List[Dict[str, Any]] = []
    cell_keys: Dict[str, Dict[str, str]] = {}
    sources: set = set()

    # Execution-time and test-set metrics apply uniformly across the whole
    # run -- resolving them per requirement group (below) still works, since
    # every group's representative resolves the same config, but showing
    # that identical result under every requirement's own header would
    # duplicate each metric once per requirement instead of once for the
    # run. Those two sources pool into one requirement-less section instead;
    # "requirement" and "none" both keep their own entry, since neither is a
    # metric shared across groups -- "requirement" is genuinely specific to
    # its own requirement, and "none" is nothing resolved at all.
    pooled_test_ids: List[str] = []
    pooled_metrics: Dict[uuid.UUID, models.Metric] = {}

    for group in groups:
        group_test_ids = tests_by_group.get(group, [])
        representative = (
            db.query(models.Test).filter(models.Test.id == uuid.UUID(group_test_ids[0])).first()
        )
        if representative is None:
            metrics, source = [], "none"
        else:
            metrics, source = get_test_metrics(
                representative,
                db,
                organization_id=organization_id,
                user_id=user_id,
                test_set=test_set,
                test_configuration=test_config,
                return_source=True,
            )
        sources.add(source)

        keyed = _assign_metric_keys(metrics)

        # "none" keeps its own entry too, not just "requirement" -- it isn't
        # a metric that applies uniformly across the run, it is a group with
        # nothing resolved at all (e.g. a requirement carrying no metric of
        # its own). Pooling it would fold that requirement's name into the
        # pooled bucket's "Unassigned" label, and if some other group's
        # test_set/execution_time metric ends up in that same bucket, would
        # wrongly attach it to this group's tests too.
        if source in ("requirement", "none"):
            requirements_payload.append(
                {
                    "id": group,
                    "name": requirement_names.get(group, "Unassigned") if group else "Unassigned",
                    "metrics": [
                        {
                            "key": key,
                            "name": metric.name or metric.class_name,
                            "id": str(metric.id) if metric.id else None,
                            "ambiguous": ambiguous,
                        }
                        for key, metric, ambiguous in keyed
                    ],
                    "test_ids": group_test_ids,
                }
            )
        else:
            pooled_test_ids.extend(group_test_ids)
            for _, metric, _ in keyed:
                if metric.id:
                    pooled_metrics[metric.id] = metric

        for test_id in group_test_ids:
            scope = (
                MetricScope.MULTI_TURN
                if is_multi_turn_by_test.get(test_id)
                else MetricScope.SINGLE_TURN
            )
            kept = filter_configs_by_scope([metric for _, metric, _ in keyed], scope, test_id)
            # Re-key the survivors the way the runtime will, so a suffix that
            # only exists because of a filtered-out sibling doesn't end up in
            # the lookup. Identical to the row key whenever no name collides.
            runtime_key_by_metric = {id(m): key for key, m, _ in _assign_metric_keys(kept)}
            row_key_by_metric = {id(m): key for key, m, _ in keyed}
            per_test = {
                _metric_ref(m, row_key_by_metric[id(m)]): runtime_key_by_metric[id(m)] for m in kept
            }
            if per_test:
                cell_keys[test_id] = per_test

    if pooled_test_ids:
        pooled_keyed = _assign_metric_keys(list(pooled_metrics.values()))
        requirements_payload.append(
            {
                "id": None,
                "name": "Unassigned",
                "metrics": [
                    {
                        "key": key,
                        "name": metric.name or metric.class_name,
                        "id": str(metric.id) if metric.id else None,
                        "ambiguous": ambiguous,
                    }
                    for key, metric, ambiguous in pooled_keyed
                ],
                "test_ids": pooled_test_ids,
            }
        )

    return {
        "source": sources.pop() if len(sources) == 1 else "mixed",
        "requirements": requirements_payload,
        "test_order": test_order,
        "cell_keys": cell_keys,
    }
