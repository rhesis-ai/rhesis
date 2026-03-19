import asyncio
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app import crud

from .utils import _build_eligible_tests, _get_test_set_tests_from_db

logger = logging.getLogger(__name__)

_EVAL_MAX_CONCURRENCY = 20


def _resolve_sdk_metrics(
    db: Session,
    organization_id: str,
    user_id: str,
    metric_names: List[str],
) -> List[Any]:
    """Resolve metric names from the DB and instantiate SDK metric objects.

    Returns a list of ready-to-use SDK ``BaseMetric`` instances.

    Raises ``ValueError`` when a requested metric name does not exist
    or none of the resolved metrics could be instantiated.
    """
    import dataclasses

    from rhesis.backend.metrics.metric_config import metric_model_to_config
    from rhesis.backend.tasks.execution.test import get_evaluation_model
    from rhesis.sdk.metrics import MetricFactory

    name_clauses = " or ".join(f"name eq '{n}'" for n in metric_names)
    resolved = crud.get_metrics(
        db,
        skip=0,
        limit=len(metric_names),
        filter=name_clauses,
        organization_id=organization_id,
    )
    found_names = {m.name for m in resolved}
    missing = [n for n in metric_names if n not in found_names]
    if missing:
        raise ValueError(f"Metric does not exist: {', '.join(missing)}")

    model = get_evaluation_model(db, user_id)

    sdk_metrics = []
    for m in resolved:
        cfg = metric_model_to_config(m)
        backend_raw = getattr(cfg.backend, "value", cfg.backend)
        backend = backend_raw if isinstance(backend_raw, str) else "rhesis"
        class_name = cfg.class_name
        if not class_name or not backend:
            continue
        params = dataclasses.asdict(cfg)
        params.pop("class_name", None)
        params.pop("backend", None)
        if model is not None:
            params["model"] = model
        try:
            metric = MetricFactory.create(backend, class_name, **params)
            sdk_metrics.append(metric)
        except Exception as exc:
            logger.warning(f"Failed to create SDK metric {class_name}: {exc}")

    if not sdk_metrics:
        raise ValueError("No valid SDK metrics could be created")

    return sdk_metrics


async def _run_metrics_on_text(
    sdk_metrics: List[Any],
    input_text: str,
    output_text: str,
) -> Dict[str, Any]:
    """Run all *sdk_metrics* against a single (input, output) pair.

    Returns a dict keyed by metric name with ``score`` and
    ``is_successful`` for each metric that succeeded.
    """
    import inspect

    metric_results: Dict[str, Any] = {}
    for metric in sdk_metrics:
        sig = inspect.signature(metric.a_evaluate)
        params = sig.parameters
        kwargs: Dict[str, Any] = {}
        if "input" in params:
            kwargs["input"] = input_text
        if "output" in params:
            kwargs["output"] = output_text
        if "expected_output" in params:
            kwargs["expected_output"] = ""
        if "context" in params:
            kwargs["context"] = []

        result = await metric.a_evaluate(**kwargs)
        is_successful = result.details.get("is_successful", result.score >= 0.5)
        metric_results[metric.name] = {
            "score": result.score,
            "is_successful": is_successful,
        }

    return metric_results


async def evaluate_tests_for_adaptive_set(
    db: Session,
    test_set_identifier: str,
    organization_id: str,
    user_id: str,
    metric_names: List[str],
    test_ids: Optional[List[UUID]] = None,
    topic: Optional[str] = None,
    include_subtopics: bool = True,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Evaluate adaptive testing tests with the specified metrics.

    Uses SDK metric instances directly via ``a_evaluate`` with up to
    ``_EVAL_MAX_CONCURRENCY`` items evaluated concurrently.

    Parameters
    ----------
    db : Session
        Database session
    test_set_identifier : str
        Test set identifier (UUID, nano_id, or slug)
    organization_id : str
        Organization ID for tenant isolation
    user_id : str
        User ID for tenant isolation
    metric_names : list of str
        Metric names to evaluate (must exist in the organization)
    test_ids : list of UUID, optional
        Limit evaluation to these test IDs
    topic : str, optional
        Limit evaluation to tests under this topic path
    include_subtopics : bool, default True
        When topic is set, include subtopics or not
    overwrite : bool, default False
        If False, tests that already have evaluation results will be skipped.

    Returns
    -------
    dict
        - evaluated: number of tests evaluated
        - skipped: number of tests skipped due to existing results
        - results: list of {test_id, label, labeler, model_score}
        - failed: list of {test_id, error}

    Raises
    ------
    ValueError
        If any metric name does not exist or the test set is not found.
    """
    sdk_metrics = _resolve_sdk_metrics(db, organization_id, user_id, metric_names)

    db_test_set = crud.resolve_test_set(test_set_identifier, db, organization_id=organization_id)
    if db_test_set is None:
        raise ValueError(f"Test set not found with identifier: {test_set_identifier}")

    tests = _get_test_set_tests_from_db(db, db_test_set.id, organization_id, user_id)
    eligible_raw = _build_eligible_tests(tests, test_ids, topic, include_subtopics)

    eligible = []
    skipped = 0
    for t in eligible_raw:
        meta = t.test_metadata or {}
        if not overwrite and meta.get("label", "").strip():
            skipped += 1
            continue
        eligible.append(t)

    async def _evaluate_test(test) -> Dict[str, Any]:
        test_id_str = str(test.id)
        input_text = (test.prompt.content or "").strip()
        output_text = (test.test_metadata or {}).get("output", "")

        if not output_text or output_text == "[no output]":
            logger.warning(
                f"Test {test_id_str} has no output to evaluate — run generate_outputs first"
            )
            return {"status": "failed", "test_id": test_id_str, "error": "no output"}

        try:
            metric_results = await _run_metrics_on_text(sdk_metrics, input_text, output_text)

            valid = {k: v for k, v in metric_results.items() if isinstance(v, dict)}

            if not valid:
                logger.warning(f"No valid metric results for test {test_id_str}")
                return {
                    "status": "failed",
                    "test_id": test_id_str,
                    "error": "no metric results",
                }

            all_passed = all(v.get("is_successful", False) for v in valid.values())
            agg_label = "pass" if all_passed else "fail"
            agg_labeler = ", ".join(metric_names)
            scores = [v.get("score", 0.0) for v in valid.values()]
            agg_score = sum(scores) / len(scores) if scores else 0.0

            meta = dict(test.test_metadata or {})
            meta["label"] = agg_label
            meta["labeler"] = agg_labeler
            meta["model_score"] = agg_score
            if len(sdk_metrics) > 1:
                meta["evaluation"] = [
                    {
                        "label": "pass" if r.get("is_successful") else "fail",
                        "labeler": r.get("name", key),
                        "model_score": r.get("score", 0.0),
                    }
                    for key, r in valid.items()
                ]
            elif "evaluation" in meta:
                del meta["evaluation"]
            test.test_metadata = meta

            return {
                "status": "ok",
                "test_id": test_id_str,
                "label": agg_label,
                "labeler": agg_labeler,
                "model_score": agg_score,
            }

        except Exception as e:
            logger.warning(
                f"Evaluation failed for test {test_id_str}: {e}",
                exc_info=True,
            )
            meta = dict(test.test_metadata or {})
            meta["label"] = "error"
            meta["labeler"] = ", ".join(metric_names)
            meta["model_score"] = 0.0
            test.test_metadata = meta
            return {
                "status": "failed",
                "test_id": test_id_str,
                "error": str(e),
            }

    semaphore = asyncio.Semaphore(_EVAL_MAX_CONCURRENCY)

    async def _bounded(test):
        async with semaphore:
            return await _evaluate_test(test)

    all_outcomes = list(await asyncio.gather(*(_bounded(t) for t in eligible)))

    db.flush()

    results = [
        {
            "test_id": o["test_id"],
            "label": o["label"],
            "labeler": o["labeler"],
            "model_score": o["model_score"],
        }
        for o in all_outcomes
        if o["status"] == "ok"
    ]
    failed = [
        {"test_id": o["test_id"], "error": o["error"]}
        for o in all_outcomes
        if o["status"] == "failed"
    ]

    logger.info(
        f"Evaluate: test_set={test_set_identifier}, "
        f"metrics={metric_names!r}, topic={topic!r}, "
        f"evaluated={len(results)}, skipped={skipped}, failed={len(failed)}"
    )

    return {
        "evaluated": len(results),
        "skipped": skipped,
        "results": results,
        "failed": failed,
    }
