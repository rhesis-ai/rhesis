"""How this report compares with the published report its author picked as baseline.

A test counts as failing on a side when any of that side's counted results for it
failed, so "newly failing" and "fixed" mean the same under every counting rule.
"""

import uuid
from typing import Any, Dict, Iterable, List, Optional, Set

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud import report as report_crud
from rhesis.backend.app.services.report.counting import CountedResult


def _failing_and_passing(rows: Iterable[Any]) -> tuple:
    failing: Set[uuid.UUID] = set()
    judged: Set[uuid.UUID] = set()
    for row in rows:
        if row.execution != "ok" or row.verdict not in ("pass", "fail"):
            continue
        judged.add(row.test_id)
        if row.verdict == "fail":
            failing.add(row.test_id)
    return failing, judged - failing


def _delta(now: Optional[float], before: Optional[float]) -> Optional[float]:
    return round(now - before, 2) if now is not None and before is not None else None


def compare(
    db: Session,
    report: models.Report,
    totals: dict,
    tree: List[dict],
    counted: List[CountedResult],
) -> Optional[Dict[str, Any]]:
    """Fills ``pass_rate_delta`` on the tree rows and returns the comparison, or None
    when the report has no baseline."""
    if report.baseline_report_id is None:
        return None
    baseline = report_crud.get_published_report(db, report.baseline_report_id)
    if baseline is None or not baseline.metrics:
        return None
    before = baseline.metrics
    before_rates = {str(row["id"]): row.get("pass_rate") for row in before.get("requirements", [])}
    for row in tree:
        row["pass_rate_delta"] = _delta(row["pass_rate"], before_rates.get(str(row["id"])))

    failing_now, passing_now = _failing_and_passing(counted)
    failing_before, passing_before = _failing_and_passing(
        report_crud.get_frozen_results(db, baseline.id)
    )
    newly_failing = failing_now & passing_before
    return {
        "baseline": {
            "id": baseline.id,
            "title": baseline.title,
            "published_at": baseline.published_at,
            "result_rule": before.get("result_rule", "latest"),
        },
        "pass_rate_delta": _delta(
            totals.get("pass_rate"), (before.get("totals") or {}).get("pass_rate")
        ),
        "newly_failing": len(newly_failing),
        "fixed": len(failing_before & passing_now),
        "newly_failing_requirements": sorted(
            {row["name"] for row in tree if _has_any(row, counted, newly_failing)}
        ),
    }


def _has_any(row: dict, counted: List[CountedResult], tests: Set[uuid.UUID]) -> bool:
    return any(r.requirement_id == row["id"] and r.test_id in tests for r in counted)
