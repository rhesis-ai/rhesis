import csv
import logging
import time
import uuid
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.crud import prompt as prompt_crud
from rhesis.backend.app.crud import test_configuration as test_configuration_crud
from rhesis.backend.app.crud import test_result as test_result_crud
from rhesis.backend.app.crud import test_run as test_run_crud
from rhesis.backend.app.crud.metric import get_requirement_metrics
from rhesis.backend.app.crud.test_run import get_test_run, get_test_run_requirements
from rhesis.backend.app.outcomes import (
    GRID_RESULT,
    NOT_APPLICABLE_CHAR,
    VERDICT_CHAR,
    Outcome,
)

logger = logging.getLogger(__name__)

# Statuses a test run never leaves -- the grid stops refetching once here.
_TERMINAL_RUN_STATUSES = {"Completed", "Partial", "Failed", "Cancelled"}

# test_status encoding: get_test_outcomes_for_run's grid-result strings
# (GRID_RESULT, the same vocabulary v_test_result_stats.result speaks),
# keyed down to the three a test (as opposed to a single metric) can be
# encoded as. VERDICT_CHAR[Outcome.PENDING] covers everything else --
# cancelled included, since the grid has no separate glyph for it.
_TEST_STATUS_CHAR = {
    GRID_RESULT[outcome]: VERDICT_CHAR[outcome]
    for outcome in (Outcome.PASS, Outcome.FAIL, Outcome.ERROR)
}

# Past this many tests the grid renders binned, where per-cell animation is
# illegible anyway -- so the timing arrays stop being worth their payload.
_TIMING_MAX_TESTS = 2000


def get_test_results_for_test_run(
    db: Session, test_run_id: uuid.UUID, organization_id: str = None
) -> List[Dict[str, Any]]:
    """
    Get all test results for a test run with related data for CSV export.

    Args:
        db: Database session
        test_run_id: UUID of the test run
        organization_id: Organization ID for security filtering

    Returns:
        List of dictionaries containing test result data
    """
    # First check if test run exists
    test_run = get_test_run(db, test_run_id, organization_id=organization_id)
    if not test_run:
        raise ValueError("Test Run not found")

    # Get test results for this test run with pagination to handle large result sets
    filter_str = f"test_run_id eq {test_run_id}"
    all_test_results = []
    skip = 0
    limit = 100  # Use maximum allowed limit

    while True:
        test_results_batch = test_result_crud.get_test_results(
            db, skip=skip, limit=limit, filter=filter_str, organization_id=organization_id
        )
        if not test_results_batch:
            break
        all_test_results.extend(test_results_batch)
        if len(test_results_batch) < limit:
            # Last batch, no more results
            break
        skip += limit

    if not all_test_results:
        raise ValueError("No test results found for this test run")

    # Get requirements and metrics for this test run with organization filtering (SECURITY CRITICAL)
    requirements = get_test_run_requirements(
        db, test_run_id, organization_id=str(test_run.organization_id)
    )

    # Create a mapping of requirement_id to requirement with metrics
    requirement_map = {}
    for requirement in requirements:
        # Get metrics for this requirement (use default limit to stay within bounds)
        # SECURITY: Pass organization_id from test_run to prevent cross-tenant access
        metrics = get_requirement_metrics(
            db, requirement.id, organization_id=str(test_run.organization_id)
        )
        requirement_map[requirement.id] = {"requirement": requirement, "metrics": metrics}

    # Process test results into CSV format
    csv_data = []

    for result in all_test_results:
        # Get related data with organization filtering
        prompt = (
            prompt_crud.get_prompt(db, result.prompt_id, organization_id=organization_id)
            if result.prompt_id
            else None
        )

        # Base row data
        row = {
            "test_id": str(result.test_id) if result.test_id else "N/A",
            "prompt_content": prompt.content if prompt else "N/A",
            "response": result.test_output.get("output", "N/A") if result.test_output else "N/A",
            "created_at": result.created_at.isoformat() if result.created_at else "N/A",
        }

        # Add requirement metrics columns
        test_metrics = result.test_metrics.get("metrics", {}) if result.test_metrics else {}

        for _requirement_id, requirement_data in requirement_map.items():
            requirement = requirement_data["requirement"]
            metrics = requirement_data["metrics"]

            for metric in metrics:
                metric_name = metric.name
                column_name = f"{requirement.name}_{metric_name}"

                # Get metric result
                metric_result = test_metrics.get(metric_name)
                if metric_result:
                    status = "Pass" if metric_result.get("is_successful") else "Fail"
                    score = metric_result.get("score", "N/A")
                    threshold = metric_result.get("threshold")
                    reference_score = metric_result.get("reference_score")
                    reason = metric_result.get("reason", "")

                    # Format based on metric type
                    if reference_score is not None:
                        # Binary/categorical metric
                        value = f"{status} ({score} vs {reference_score})"
                    elif threshold is not None:
                        # Numeric metric
                        value = f"{status} ({score}/{threshold})"
                    else:
                        # Generic metric
                        value = f"{status} ({score})"

                    if reason:
                        value += f" - {reason}"

                    row[column_name] = value
                else:
                    row[column_name] = "N/A"

        csv_data.append(row)

    return csv_data


def test_run_results_to_csv(test_results_data: List[Dict[str, Any]]) -> str:
    """
    Convert test run results data to CSV format.

    Args:
        test_results_data: List of dictionaries containing test result data

    Returns:
        CSV string
    """
    if not test_results_data:
        raise ValueError("No test results data to convert to CSV")

    # Get all unique column names
    all_columns = set()
    for row in test_results_data:
        all_columns.update(row.keys())

    # Order columns: base columns first, then requirement metrics
    base_columns = ["test_id", "prompt_content", "response", "created_at"]
    metric_columns = sorted([col for col in all_columns if col not in base_columns])
    ordered_columns = base_columns + metric_columns

    # Generate CSV
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=ordered_columns, extrasaction="ignore")

    writer.writeheader()
    for row in test_results_data:
        writer.writerow(row)

    return output.getvalue()


def rescore_test_run(
    db: Session,
    reference_test_run_id: str,
    current_user: models.User,
    metrics: Optional[List[Dict[str, Any]]] = None,
    evaluation_model_id: uuid.UUID = None,
) -> Dict[str, Any]:
    """Create a new test run that re-scores an existing one.

    No endpoints are invoked -- only metric evaluation on stored outputs.

    Args:
        db: Database session
        reference_test_run_id: UUID string of the test run to re-score
        current_user: Current authenticated user
        metrics: Optional list of execution-time metrics to use.
            Each dict should have: id, name, and optionally scope.
            If None, re-uses the original test run's metrics.

    Returns:
        Dict containing new test_run_id and status

    Raises:
        ValueError: If the reference test run is not found
    """
    org_id = str(current_user.organization_id)
    uid = str(current_user.id)

    # 1. Load the reference test run
    ref_run = get_test_run(
        db,
        test_run_id=uuid.UUID(reference_test_run_id),
        organization_id=org_id,
        user_id=uid,
    )
    if not ref_run:
        raise ValueError(f"Test run {reference_test_run_id} not found")

    ref_config = ref_run.test_configuration
    if not ref_config:
        raise ValueError(f"Test run {reference_test_run_id} has no test configuration")

    # 2. Build attributes for the new test configuration
    attributes = {
        "reference_test_run_id": reference_test_run_id,
        "is_rescore": True,
        "execution_mode": "Parallel",
    }

    if metrics:
        attributes["metrics"] = metrics
        from rhesis.backend.app.schemas.test_set import MetricsSource

        attributes["metrics_source"] = MetricsSource.EXECUTION_TIME.value
        logger.debug(f"Rescore using {len(metrics)} execution-time metrics")

    if evaluation_model_id:
        attributes["evaluation_model_id"] = str(evaluation_model_id)
        logger.debug(f"Rescore evaluation model override: {evaluation_model_id}")

    # 3. Create new TestConfiguration pointing to same endpoint/test_set
    new_config = schemas.TestConfigurationCreate(
        endpoint_id=ref_config.endpoint_id,
        test_set_id=ref_config.test_set_id,
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        attributes=attributes,
    )
    db_new_config = test_configuration_crud.create_test_configuration(
        db=db,
        test_configuration=new_config,
        organization_id=org_id,
        user_id=uid,
    )
    new_config_id = str(db_new_config.id)
    logger.info(
        f"Created rescore test configuration {new_config_id} "
        f"for reference run {reference_test_run_id}"
    )

    # 4. Submit for execution via the task launcher
    from rhesis.backend.jobs import launch_job
    from rhesis.backend.jobs.test_configuration import (
        execute_test_configuration,
    )

    result = launch_job(
        execute_test_configuration,
        new_config_id,
        current_user=current_user,
        db=db,
    )

    logger.info(f"Rescore submitted for reference run {reference_test_run_id}, task {result.id}")

    return {
        "status": "submitted",
        "message": (f"Re-scoring test run {reference_test_run_id} with new metrics"),
        "test_configuration_id": new_config_id,
        "reference_test_run_id": reference_test_run_id,
        "task_id": result.id,
    }


def _is_newer(candidate: Any, incumbent: Any) -> bool:
    """Whether ``candidate`` should displace ``incumbent`` as a cell's verdict.

    An undated row never displaces a dated one (the view's ``created_at`` is
    non-null in practice; this only decides the degenerate case rather than
    letting it silently reorder results).
    """
    if candidate is None:
        return False
    if incumbent is None:
        return True
    return candidate >= incumbent


def _fallback_plan_from_results(
    db: Session, test_run: models.TestRun, organization_id: Optional[str]
) -> Dict[str, Any]:
    """Best-effort plan for a run dispatched before the metric-plan snapshot shipped.

    Derives rows from metrics that were actually recorded rather than what
    would be planned prospectively -- this module must not import ``jobs/``
    (see ``apps/backend/AGENTS.md``'s layering rule), and the prospective
    planner lives in ``jobs/execution/metric_plan.py``, run at dispatch time.
    Not-applicable (scope-filtered) cells are not reconstructed: a legacy
    run just never shows an ``X``, which is a fine degradation for runs old
    enough to predate this feature.
    """
    test_config = test_run.test_configuration
    test_set_id = test_config.test_set_id if test_config else None
    ordered = (
        test_run_crud.get_ordered_tests_for_test_set(db, test_set_id, organization_id)
        if test_set_id
        else []
    )
    test_order = [test_id for test_id, _, _ in ordered]
    requirement_by_test = {test_id: req_id for test_id, req_id, _ in ordered}

    tests_by_group: Dict[Optional[str], List[str]] = {}
    for test_id, req_id, _ in ordered:
        tests_by_group.setdefault(req_id, []).append(test_id)

    verdict_rows = test_run_crud.get_metric_verdicts_for_run(
        db, test_run.id, organization_id=organization_id
    )

    metrics_by_group: Dict[Optional[str], List[str]] = {}
    cell_keys: Dict[str, Dict[str, str]] = {}
    for row in verdict_rows:
        test_id = str(row.test_id)
        req_id = str(row.requirement_id) if row.requirement_id else requirement_by_test.get(test_id)
        names = metrics_by_group.setdefault(req_id, [])
        if row.metric_name not in names:
            names.append(row.metric_name)
        # A recorded row is its own evidence that the metric applied to this
        # test, and the key it applied under is the name itself -- the
        # runtime already resolved any suffix before writing the JSONB.
        cell_keys.setdefault(test_id, {})[row.metric_name] = row.metric_name

    requirement_ids = [req_id for req_id in metrics_by_group if req_id is not None]
    requirement_names = _requirement_names_for_fallback(db, requirement_ids, organization_id)

    # A test that produced no verdict row yet still needs its own group's
    # metrics marked applicable, or every unexecuted column would read as
    # not-applicable instead of pending.
    for req_id, metric_names in metrics_by_group.items():
        for test_id in tests_by_group.get(req_id, []):
            per_test = cell_keys.setdefault(test_id, {})
            for name in metric_names:
                per_test.setdefault(name, name)

    requirements_payload = [
        {
            "id": req_id,
            "name": requirement_names.get(req_id, "Unassigned") if req_id else "Unassigned",
            "metrics": [
                {"key": name, "name": name, "id": None, "ambiguous": False}
                for name in sorted(metric_names)
            ],
            "test_ids": tests_by_group.get(req_id, []),
        }
        for req_id, metric_names in metrics_by_group.items()
    ]

    return {
        "source": "legacy",
        "requirements": requirements_payload,
        "test_order": test_order,
        "cell_keys": cell_keys,
    }


def _requirement_names_for_fallback(
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


def _build_timing_columns(
    test_run_id: uuid.UUID, test_order: List[str]
) -> Tuple[
    Optional[List[Optional[int]]],
    Optional[List[Optional[int]]],
    Optional[List[Optional[int]]],
    Optional[int],
]:
    """Phase-offset columns aligned to test_order, plus the run's elapsed time.

    All-None on any failure: the timing cache is a nicety for the animation,
    never a reason to fail the grid.
    """
    if not test_order or len(test_order) > _TIMING_MAX_TESTS:
        return None, None, None, None

    try:
        from rhesis.backend.app.services.test_run_timing import get_test_run_timing_cache

        origin, timings = get_test_run_timing_cache().get_run_timing(str(test_run_id))
    except Exception:
        logger.debug("verdict matrix: timing lookup failed", exc_info=True)
        return None, None, None, None

    if origin is None:
        return None, None, None, None

    # An origin with no phases yet means the run has just been picked up.
    # Report elapsed anyway so the client's clock can start reconciling
    # against the server from its very first poll.
    elapsed_ds = max(0, int(round((time.time() - origin) * 10)))
    if not timings:
        return None, None, None, elapsed_ds

    started: List[Optional[int]] = []
    generated: List[Optional[int]] = []
    resolved: List[Optional[int]] = []
    for test_id in test_order:
        entry = timings.get(test_id)
        started.append(entry.started_ds if entry else None)
        generated.append(entry.generated_ds if entry else None)
        resolved.append(entry.resolved_ds if entry else None)

    return started, generated, resolved, elapsed_ds


def get_verdict_matrix(
    db: Session,
    test_run: models.TestRun,
    columns: Optional[str] = None,
) -> schemas.VerdictMatrix:
    """Build the encoded verdict grid for a test run.

    One row per (requirement, metric); each row's ``verdicts`` string has one
    character per test in ``test_ids``' order: ``.`` pending, ``P`` passed,
    ``F`` failed, ``S`` scored with no pass/fail threshold, ``E`` execution
    error, ``X`` not applicable to that test.
    """
    org_id = str(test_run.organization_id) if test_run.organization_id else None
    attributes = test_run.attributes or {}
    plan = attributes.get("metric_plan")
    if not plan:
        plan = _fallback_plan_from_results(db, test_run, org_id)

    test_order: List[str] = plan.get("test_order", [])
    cell_keys: Dict[str, Dict[str, str]] = plan.get("cell_keys", {})

    verdict_rows = test_run_crud.get_metric_verdicts_for_run(
        db, test_run.id, organization_id=org_id
    )
    # Keep the newest row per (test, metric). A test can hold more than one
    # test_result in a run (a rescore, or a duplicate persist), and
    # get_test_outcomes_for_run already resolves to the latest -- letting an
    # arbitrary row win here would show a stale verdict beside a current
    # status for the same test.
    verdict_index: Dict[Tuple[str, str], Tuple[Optional[bool], bool]] = {}
    verdict_seen_at: Dict[Tuple[str, str], Any] = {}
    for row in verdict_rows:
        cell = (str(row.test_id), row.metric_name)
        if cell in verdict_seen_at and not _is_newer(row.created_at, verdict_seen_at[cell]):
            continue
        verdict_seen_at[cell] = row.created_at
        verdict_index[cell] = (row.effective_success, bool(row.has_override))

    outcomes = test_run_crud.get_test_outcomes_for_run(db, test_run.id, organization_id=org_id)
    reviews_count = test_run_crud.get_review_count_for_run(db, test_run.id, organization_id=org_id)

    requirements_payload: List[schemas.VerdictRequirement] = []
    rows_payload: List[schemas.VerdictRow] = []

    verdicts_resolved = 0
    verdicts_planned = 0

    for group in plan.get("requirements", []):
        req_id = group.get("id")
        metrics = group.get("metrics", [])
        requirements_payload.append(
            schemas.VerdictRequirement(
                id=req_id,
                name=group.get("name", "Unassigned"),
                metric_keys=[m["key"] for m in metrics],
            )
        )

        # A row belongs to one requirement, so every column outside that
        # requirement's own tests is structurally not-applicable. Without
        # this the row would claim the whole run's width and -- when another
        # requirement carries a same-named metric -- read that requirement's
        # verdicts as its own, since verdict_index is keyed on
        # (test_id, jsonb_key) with no requirement dimension.
        group_test_ids = set(group.get("test_ids", test_order))

        for metric in metrics:
            key = metric["key"]
            name = metric["name"]
            metric_ref = metric.get("id") or key
            chars: List[str] = []
            override_chars: List[str] = []
            passed = failed = pending = 0

            for test_id in test_order:
                if test_id not in group_test_ids:
                    chars.append(NOT_APPLICABLE_CHAR)
                    override_chars.append("0")
                    continue

                # Absent from cell_keys = scope-filtered out for this test.
                actual_key = cell_keys.get(test_id, {}).get(metric_ref)
                if actual_key is None:
                    chars.append(NOT_APPLICABLE_CHAR)
                    override_chars.append("0")
                    continue

                verdicts_planned += 1
                entry = verdict_index.get((test_id, actual_key))
                if entry is not None:
                    effective_success, has_override = entry
                    verdicts_resolved += 1
                    override_chars.append("1" if has_override else "0")
                    if effective_success is True:
                        chars.append(VERDICT_CHAR[Outcome.PASS])
                        passed += 1
                    elif effective_success is False:
                        chars.append(VERDICT_CHAR[Outcome.FAIL])
                        failed += 1
                    else:
                        chars.append(VERDICT_CHAR[Outcome.INCONCLUSIVE])
                elif outcomes.get(test_id) == GRID_RESULT[Outcome.ERROR]:
                    chars.append(VERDICT_CHAR[Outcome.ERROR])
                    override_chars.append("0")
                    verdicts_resolved += 1
                else:
                    chars.append(VERDICT_CHAR[Outcome.PENDING])
                    override_chars.append("0")
                    pending += 1

            rows_payload.append(
                schemas.VerdictRow(
                    requirement_id=req_id,
                    metric_key=key,
                    metric_name=name,
                    metric_id=metric.get("id"),
                    ambiguous=metric.get("ambiguous", False),
                    verdicts="".join(chars),
                    overrides="".join(override_chars),
                    passed=passed,
                    failed=failed,
                    pending=pending,
                )
            )

    # A cancelled or still-pending test counts as neither, so these two need
    # not sum to tests_executed.
    _FAILING_RESULTS = (GRID_RESULT[Outcome.FAIL], GRID_RESULT[Outcome.ERROR])
    tests_executed = sum(1 for test_id in test_order if test_id in outcomes)
    passing_tests = sum(
        1 for test_id in test_order if outcomes.get(test_id) == GRID_RESULT[Outcome.PASS]
    )
    failing_tests = sum(1 for test_id in test_order if outcomes.get(test_id) in _FAILING_RESULTS)
    # Pass rate is over tests, not over metric verdicts, to agree with the
    # number the runs list and the run header already show
    # (result_processor.get_test_statistics_for_runs). A test with four of
    # five metrics passing is a failed test, but an 80% verdict rate -- the
    # Summary tab reporting the latter would contradict every other view of
    # the same run. Per-metric pass counts stay on each row.
    pass_rate = (
        passing_tests / (passing_tests + failing_tests) if (passing_tests + failing_tests) else None
    )

    status_name = test_run.status.name if test_run.status else ""

    # Always sent, unlike test_ids: this is the part that actually changes
    # between polls while a run is in flight.
    started_ds, generated_ds, resolved_ds, elapsed_ds = _build_timing_columns(
        test_run.id, test_order
    )

    return schemas.VerdictMatrix(
        test_run_id=test_run.id,
        project_id=test_run.project_id,
        status=status_name,
        is_terminal=status_name in _TERMINAL_RUN_STATUSES,
        test_ids=None if columns == "none" else [uuid.UUID(tid) for tid in test_order],
        test_status="".join(
            _TEST_STATUS_CHAR.get(outcomes.get(tid, ""), VERDICT_CHAR[Outcome.PENDING])
            for tid in test_order
        ),
        test_started_ds=started_ds,
        test_generated_ds=generated_ds,
        test_resolved_ds=resolved_ds,
        elapsed_ds=elapsed_ds,
        requirements=requirements_payload,
        rows=rows_payload,
        kpis=schemas.VerdictKpis(
            pass_rate=pass_rate,
            tests_executed=tests_executed,
            tests_total=len(test_order),
            verdicts_resolved=verdicts_resolved,
            verdicts_planned=verdicts_planned,
            failures=failing_tests,
            reviews_count=reviews_count,
        ),
    )
