"""Test run statistics using the v_test_run_stats database view."""

from typing import Any, Dict, List, Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from rhesis.backend.app.constants import OverallTestResult
from rhesis.backend.app.models.stats_views import TestResultStatsView, TestRunStatsView

from .common import (
    build_empty_stats_response,
    build_metadata,
    build_response_data,
    parse_date_range,
)

MODE_DEFINITIONS = {
    "all": [
        "status_distribution",
        "result_distribution",
        "most_run_test_sets",
        "top_executors",
        "timeline",
        "overall_summary",
    ],
    "status": ["status_distribution"],
    "results": ["result_distribution"],
    "test_sets": ["most_run_test_sets"],
    "executors": ["top_executors"],
    "timeline": ["timeline"],
    "summary": ["overall_summary"],
}

V = TestRunStatsView


def _apply_filters(query, *, organization_id, start_date_obj, end_date_obj, **kw):
    """Apply filters directly on the pre-joined view columns."""
    if organization_id:
        query = query.filter(V.organization_id == organization_id)
    if start_date_obj:
        query = query.filter(V.created_at >= start_date_obj)
    if end_date_obj:
        query = query.filter(V.created_at <= end_date_obj)
    if kw.get("test_run_ids"):
        query = query.filter(V.test_run_id.in_(kw["test_run_ids"]))
    if kw.get("user_ids"):
        query = query.filter(V.user_id.in_(kw["user_ids"]))
    if kw.get("endpoint_ids"):
        query = query.filter(V.endpoint_id.in_(kw["endpoint_ids"]))
    if kw.get("test_set_ids"):
        query = query.filter(V.test_set_id.in_(kw["test_set_ids"]))
    if kw.get("status_list"):
        query = query.filter(V.status_name.in_(kw["status_list"]))
    return query


def _get_stats(db: Session, filters: dict, mode: str, top: Optional[int]) -> Dict[str, Any]:
    """Build all requested stat sections via simple GROUP BY queries on the view."""

    def base():
        return _apply_filters(db.query(V), **filters)

    stats: Dict[str, Any] = {}

    if mode in ("all", "status", "summary"):
        q = (
            base()
            .with_entities(V.status_name, func.count().label("count"))
            .group_by(V.status_name)
            .order_by(desc("count"))
        )
        if top:
            q = q.limit(top)
        stats["status_distribution"] = [
            {"status": r.status_name, "count": r.count} for r in q.all()
        ]

    if mode in ("all", "results", "summary"):
        VR = TestResultStatsView
        matching_run_ids = base().with_entities(V.test_run_id).distinct()
        q = db.query(
            func.count().label("total"),
            func.count().filter(VR.result == OverallTestResult.PASSED).label("passed"),
            func.count().filter(VR.result == OverallTestResult.FAILED).label("failed"),
            func.count().filter(VR.result == OverallTestResult.PENDING).label("pending"),
        ).filter(VR.test_run_id.in_(matching_run_ids))
        if filters.get("organization_id"):
            q = q.filter(VR.organization_id == filters["organization_id"])
        r = q.one()
        total = r.total or 0
        passed = r.passed or 0
        failed = r.failed or 0
        pending = r.pending or 0
        evaluated = passed + failed  # pending results excluded from pass_rate
        stats["result_distribution"] = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pending": pending,
            "pass_rate": round((passed / evaluated) * 100, 2) if evaluated > 0 else 0,
        }

    if mode in ("all", "test_sets"):
        q = (
            base()
            .with_entities(V.test_set_name, func.count().label("run_count"))
            .filter(V.test_set_name.isnot(None))
            .group_by(V.test_set_name)
            .order_by(desc("run_count"))
        )
        if top:
            q = q.limit(top)
        stats["most_run_test_sets"] = [
            {"test_set_name": r.test_set_name, "run_count": r.run_count} for r in q.all()
        ]

    if mode in ("all", "executors"):
        q = (
            base()
            .with_entities(V.executor_name, func.count().label("run_count"))
            .filter(V.executor_name.isnot(None))
            .group_by(V.executor_name)
            .order_by(desc("run_count"))
        )
        if top:
            q = q.limit(top)
        stats["top_executors"] = [
            {"executor_name": r.executor_name, "run_count": r.run_count} for r in q.all()
        ]

    if mode in ("all", "timeline"):
        q = (
            base()
            .with_entities(
                V.year,
                V.month,
                func.count().label("total_runs"),
                func.count().filter(V.result == OverallTestResult.PASSED).label("passed"),
                func.count().filter(V.result == OverallTestResult.FAILED).label("failed"),
            )
            .group_by(V.year, V.month)
            .order_by(V.year, V.month)
        )
        timeline = []
        for r in q.all():
            month_key = f"{r.year:04d}-{r.month:02d}"
            pending = r.total_runs - r.passed - r.failed
            timeline.append(
                {
                    "date": month_key,
                    "total_runs": r.total_runs,
                    "result_breakdown": {
                        "passed": r.passed,
                        "failed": r.failed,
                        "pending": pending,
                    },
                }
            )
        stats["timeline"] = timeline

    return stats


def get_test_run_stats(
    db: Session,
    organization_id: str | None = None,
    months: int = 6,
    mode: str = "all",
    top: int | None = None,
    test_run_ids: List[str] | None = None,
    user_ids: List[str] | None = None,
    endpoint_ids: List[str] | None = None,
    test_set_ids: List[str] | None = None,
    status_list: List[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> Dict:
    """Get test run statistics. Signature kept identical for backward compatibility."""

    start_date_obj, end_date_obj = parse_date_range(start_date, end_date, months)

    filters = {
        "organization_id": organization_id,
        "start_date_obj": start_date_obj,
        "end_date_obj": end_date_obj,
        "test_run_ids": test_run_ids,
        "user_ids": user_ids,
        "endpoint_ids": endpoint_ids,
        "test_set_ids": test_set_ids,
        "status_list": status_list,
    }

    aggregated = _get_stats(db, filters, mode, top)

    # Derive total_runs from run-level sections (not result_distribution which counts test results)
    total_runs = 0
    if "status_distribution" in aggregated:
        total_runs = sum(s["count"] for s in aggregated["status_distribution"])
    elif "timeline" in aggregated:
        total_runs = sum(m["total_runs"] for m in aggregated["timeline"])
    else:
        total_runs = _apply_filters(db.query(func.count(V.test_run_id)), **filters).scalar() or 0

    if total_runs == 0:
        return build_empty_stats_response(
            mode=mode,
            mode_definitions=MODE_DEFINITIONS,
            start_date_obj=start_date_obj,
            end_date_obj=end_date_obj,
            months=months,
            organization_id=organization_id,
            total_test_runs=0,
            available_statuses=[],
            available_test_sets=[],
            available_executors=[],
        )

    # Add percentages to status distribution
    if "status_distribution" in aggregated:
        for item in aggregated["status_distribution"]:
            item["percentage"] = round((item["count"] / total_runs) * 100, 2) if total_runs else 0

    # Build overall summary
    if mode in ("all", "summary"):
        most_common = "unknown"
        if aggregated.get("status_distribution"):
            most_common = max(aggregated["status_distribution"], key=lambda x: x["count"])["status"]
        aggregated["overall_summary"] = {
            "total_runs": total_runs,
            "unique_test_sets": len(aggregated.get("most_run_test_sets", [])),
            "unique_executors": len(aggregated.get("top_executors", [])),
            "most_common_status": most_common,
            "pass_rate": aggregated.get("result_distribution", {}).get("pass_rate", 0),
        }

    metadata = build_metadata(
        organization_id=organization_id,
        start_date_obj=start_date_obj,
        end_date_obj=end_date_obj,
        months=months,
        mode=mode,
        total_items=total_runs,
        total_test_runs=total_runs,
        available_statuses=[s["status"] for s in aggregated.get("status_distribution", [])],
        available_test_sets=[
            ts["test_set_name"] for ts in aggregated.get("most_run_test_sets", [])
        ],
        available_executors=[e["executor_name"] for e in aggregated.get("top_executors", [])],
    )

    return build_response_data(
        mode,
        MODE_DEFINITIONS,
        status_distribution=aggregated.get("status_distribution", []),
        result_distribution=aggregated.get("result_distribution", {}),
        most_run_test_sets=aggregated.get("most_run_test_sets", []),
        top_executors=aggregated.get("top_executors", []),
        timeline=aggregated.get("timeline", []),
        overall_summary=aggregated.get("overall_summary", {}),
        metadata=metadata,
    )
