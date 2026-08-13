"""Tuning runs: running a metric over its own cases.

A run creates no rows in the execution tables -- no test run, no test
configuration, no endpoint, no metric row for the comparison. It is this service
plus a background task, writing into JSONB that already exists: the per-case
result onto the case's ``test_metadata``, the run summary onto the tuning test
set's ``attributes``. domain.local/adr/0004 records why, and what was rejected.

Only the latest run is kept. A new run overwrites the previous results outright
rather than appending -- trend over time deserves real rows, not an unbounded
blob in a column nothing paginates, and nothing is lost that re-running cannot
recover.

Nothing starts a run on its own. Every run costs one LLM call per case, so
editing a case or an evaluation prompt must never turn into a bill for someone
who does not know a tuning set exists.
"""

import logging
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud import metric_tuning as crud_metric_tuning
from rhesis.backend.app.schemas.metric_tuning_metadata import (
    MetricTuningCaseResult,
    MetricTuningRunSummary,
    TuningRunStatus,
)
from rhesis.backend.app.services.metric_tuning.invoke import invoke_metric_on_case
from rhesis.backend.app.services.metric_tuning.payload import parse_payload
from rhesis.backend.app.services.metric_tuning.test_sets import get_tuning_test_set

logger = logging.getLogger(__name__)


class NoTuningCases(Exception):
    """A run was asked for on a metric that has nothing to run over."""


class TuningRunInFlight(Exception):
    """A run was asked for while one is already going."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_tuning_run(db: Session, metric: models.Metric, organization_id: str):
    """The metric's latest run. ``never_run`` when there has not been one."""
    test_set = get_tuning_test_set(db, metric.id, organization_id)
    if not test_set:
        return MetricTuningRunSummary()
    return crud_metric_tuning.get_run_summary(test_set)


def start_tuning_run(
    db: Session, metric: models.Metric, organization_id: str
) -> MetricTuningRunSummary:
    """Claim the run slot and return the summary the caller should show.

    Only marks the run as started -- the work itself happens in the background
    task, which is dispatched by the caller once this has been committed.

    The refusal while a run is in flight is advisory: the stored status is the
    only check, so two requests in the same instant can both pass. The failure
    mode is a summary belonging to neither run rather than corruption, which is
    the trade ADR-0004 accepts for a flagged feature. Making it actually safe is
    its own ticket.
    """
    test_set = get_tuning_test_set(db, metric.id, organization_id)
    if not test_set:
        raise NoTuningCases("This metric has no tuning cases yet. Add one before running it.")

    cases = crud_metric_tuning.get_tuning_cases(db, test_set.id, organization_id)
    if not cases:
        raise NoTuningCases("This metric has no tuning cases yet. Add one before running it.")

    current = crud_metric_tuning.get_run_summary(test_set)
    if current.status == TuningRunStatus.RUNNING:
        raise TuningRunInFlight("A run is already in progress for this metric.")

    summary = MetricTuningRunSummary(
        status=TuningRunStatus.RUNNING,
        started_at=_now(),
        total_cases=len(cases),
        completed_cases=0,
        errored_cases=0,
    )
    crud_metric_tuning.set_run_summary(db, test_set, summary)
    return summary


def _clear_previous_results(db: Session, cases: List[models.Test]) -> None:
    """Drop the last run's per-case results before this one writes its own.

    Without this, a case the metric now fails to reach would still be showing
    what it said last time, next to a summary describing the current run.
    """
    for db_test in cases:
        crud_metric_tuning.set_case_result(db, db_test, MetricTuningCaseResult())


def execute_tuning_run(
    db: Session, metric: models.Metric, organization_id: str
) -> MetricTuningRunSummary:
    """Run the metric over every one of its cases, writing results as it goes.

    Commits after each case so the interface can watch progress rather than
    waiting for the whole set, and so a worker that dies mid-run leaves the
    cases it did finish behind.

    A case whose metric call fails is recorded as errored and the run carries on
    -- one unreachable provider must not cost the results of every other case.
    """
    test_set = get_tuning_test_set(db, metric.id, organization_id)
    if not test_set:
        raise NoTuningCases("This metric has no tuning cases yet.")

    cases = crud_metric_tuning.get_tuning_cases(db, test_set.id, organization_id)
    if not cases:
        raise NoTuningCases("This metric has no tuning cases yet.")

    summary = crud_metric_tuning.get_run_summary(test_set)
    summary.status = TuningRunStatus.RUNNING
    summary.total_cases = len(cases)
    summary.completed_cases = 0
    summary.errored_cases = 0
    summary.completed_at = None
    summary.error = None
    if not summary.started_at:
        summary.started_at = _now()

    _clear_previous_results(db, cases)
    crud_metric_tuning.set_run_summary(db, test_set, summary)
    db.commit()

    for db_test in cases:
        payload = parse_payload(db_test.prompt.content if db_test.prompt else None)
        result = invoke_metric_on_case(db, metric, payload, organization_id)

        crud_metric_tuning.set_case_result(db, db_test, result)
        summary.completed_cases += 1
        if result.error:
            summary.errored_cases += 1
        crud_metric_tuning.set_run_summary(db, test_set, summary)
        db.commit()

    summary.status = TuningRunStatus.COMPLETED
    summary.completed_at = _now()
    crud_metric_tuning.set_run_summary(db, test_set, summary)
    db.commit()

    logger.info(
        "Tuning run for metric %s finished: %s cases, %s errored",
        metric.id,
        summary.completed_cases,
        summary.errored_cases,
    )
    return summary


def fail_tuning_run(db: Session, metric: models.Metric, organization_id: str, message: str) -> None:
    """Mark the run failed so the interface stops reading old numbers as new.

    A run that dies without this stays ``running`` forever, which both looks
    like progress and blocks the next run.
    """
    test_set = get_tuning_test_set(db, metric.id, organization_id)
    if not test_set:
        return
    summary = crud_metric_tuning.get_run_summary(test_set)
    summary.status = TuningRunStatus.FAILED
    summary.completed_at = _now()
    summary.error = message
    crud_metric_tuning.set_run_summary(db, test_set, summary)
    db.commit()
