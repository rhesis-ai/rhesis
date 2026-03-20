"""Test result statistics using the v_test_result_stats database view."""

from datetime import datetime
from typing import Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from rhesis.backend.app.constants import TestResultStatus
from rhesis.backend.app.models.stats_views import TestResultStatsView

from .common import build_pass_rate_stats, build_response_data, parse_date_range

MODE_DEFINITIONS = {
    "all": [
        "metric_pass_rates",
        "behavior_pass_rates",
        "category_pass_rates",
        "topic_pass_rates",
        "overall_pass_rates",
        "timeline",
        "test_run_summary",
    ],
    "metrics": ["metric_pass_rates"],
    "behavior": ["behavior_pass_rates"],
    "category": ["category_pass_rates"],
    "topic": ["topic_pass_rates"],
    "overall": ["overall_pass_rates"],
    "timeline": ["timeline"],
    "test_runs": ["test_run_summary"],
    "summary": ["overall_pass_rates"],
}

V = TestResultStatsView


def _apply_filters(query, db, **f):
    """Apply filters on the pre-joined view. Most are direct column filters;
    test_set_ids and tags require lightweight subqueries."""
    if f.get("organization_id"):
        query = query.filter(V.organization_id == f["organization_id"])

    combined_run_ids = []
    if f.get("test_run_id"):
        combined_run_ids.append(f["test_run_id"])
    if f.get("test_run_ids"):
        combined_run_ids.extend(f["test_run_ids"])
    if combined_run_ids:
        query = query.filter(V.test_run_id.in_(combined_run_ids))

    if f.get("start_date_obj"):
        query = query.filter(V.created_at >= f["start_date_obj"])
    if f.get("end_date_obj"):
        query = query.filter(V.created_at <= f["end_date_obj"])

    # Direct column filters on view (no joins needed)
    direct_filters = [
        ("behavior_ids", V.behavior_id),
        ("category_ids", V.category_id),
        ("topic_ids", V.topic_id),
        ("status_ids", V.test_status_id),
        ("test_ids", V.test_id),
        ("test_type_ids", V.test_type_id),
        ("user_ids", V.test_user_id),
        ("assignee_ids", V.assignee_id),
        ("owner_ids", V.owner_id),
        ("prompt_ids", V.prompt_id),
    ]
    for key, col in direct_filters:
        if col is not None and f.get(key):
            query = query.filter(col.in_(f[key]))

    if f.get("priority_min") is not None:
        query = query.filter(V.priority >= f["priority_min"])
    if f.get("priority_max") is not None:
        query = query.filter(V.priority <= f["priority_max"])

    # test_set_ids: many-to-many via association table (subquery)
    if f.get("test_set_ids"):
        from rhesis.backend.app.models.test import test_test_set_association as assoc

        sub = (
            db.query(assoc.c.test_id).filter(assoc.c.test_set_id.in_(f["test_set_ids"])).subquery()
        )
        query = query.filter(V.test_id.in_(db.query(sub.c.test_id)))

    # tags: polymorphic via tagged_item + tag (subquery)
    if f.get("tags"):
        from rhesis.backend.app.models.tag import Tag, TaggedItem

        sub = (
            db.query(TaggedItem.entity_id)
            .join(Tag, TaggedItem.tag_id == Tag.id)
            .filter(TaggedItem.entity_type == "Test", Tag.name.in_(f["tags"]))
            .subquery()
        )
        query = query.filter(V.test_id.in_(db.query(sub.c.entity_id)))

    return query


def _overall_stats(db, base_q):
    r = base_q.with_entities(
        func.count().label("total"),
        func.count().filter(V.result == TestResultStatus.PASSED).label("passed"),
        func.count().filter(V.result == TestResultStatus.FAILED).label("failed"),
    ).one()
    total = r.total or 0
    passed = r.passed or 0
    failed = r.failed or 0
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round((passed / total) * 100, 2) if total > 0 else 0,
    }


def _timeline_stats(base_q):
    rows = base_q.with_entities(
        V.year, V.month, V.result, V.test_metrics,
    ).all()

    monthly: dict = {}
    for r in rows:
        if not r.year or not r.month:
            continue
        key = f"{r.year:04d}-{r.month:02d}"
        P, F = TestResultStatus.PASSED, TestResultStatus.FAILED
        if key not in monthly:
            monthly[key] = {P: 0, F: 0, "metrics": {}}
        bucket = monthly[key]
        if r.result == P:
            bucket[P] += 1
        elif r.result == F:
            bucket[F] += 1

        if r.test_metrics and isinstance(r.test_metrics, dict):
            metrics = r.test_metrics.get("metrics")
            if isinstance(metrics, dict):
                for name, data in metrics.items():
                    if not isinstance(data, dict) or "is_successful" not in data:
                        continue
                    if name not in bucket["metrics"]:
                        bucket["metrics"][name] = {P: 0, F: 0}
                    if data["is_successful"]:
                        bucket["metrics"][name][P] += 1
                    else:
                        bucket["metrics"][name][F] += 1

    timeline = []
    for key in sorted(monthly):
        b = monthly[key]
        passed, failed = b[TestResultStatus.PASSED], b[TestResultStatus.FAILED]
        total = passed + failed
        timeline.append(
            {
                "date": key,
                "overall": {
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "pass_rate": round((passed / total) * 100, 2) if total > 0 else 0,
                },
                "metrics": build_pass_rate_stats(b["metrics"]),
            }
        )
    return timeline


def _dimensional_stats(base_q, name_col):
    """Pass rate grouped by a pre-joined name column (behavior_name, category_name, topic_name)."""
    q = base_q.with_entities(
        name_col.label("name"),
        func.count().filter(V.result == TestResultStatus.PASSED).label("passed"),
        func.count().filter(V.result == TestResultStatus.FAILED).label("failed"),
    ).group_by(name_col)

    stats = {}
    for r in q.all():
        label = r.name or "Unknown"
        stats[label] = {"passed": r.passed or 0, "failed": r.failed or 0}
    return build_pass_rate_stats(stats)


def _test_run_summary(base_q):
    q = (
        base_q.with_entities(
            V.run_id,
            V.test_run_name,
            V.test_run_created_at,
            func.count().filter(V.result == TestResultStatus.PASSED).label("passed"),
            func.count().filter(V.result == TestResultStatus.FAILED).label("failed"),
        )
        .group_by(V.run_id, V.test_run_name, V.test_run_created_at)
        .order_by(V.test_run_created_at.desc())
    )
    summary = []
    for r in q.all():
        total = (r.passed or 0) + (r.failed or 0)
        summary.append(
            {
                "id": str(r.run_id),
                "name": r.test_run_name or f"Test Run {str(r.run_id)[:8]}",
                "created_at": r.test_run_created_at.isoformat() if r.test_run_created_at else None,
                "overall": {
                    "total": total,
                    "passed": r.passed or 0,
                    "failed": r.failed or 0,
                    "pass_rate": round((r.passed / total) * 100, 2) if total > 0 else 0,
                },
                "metrics": {},
                "total_tests": total,
            }
        )
    return summary


def _metric_stats(base_q):
    """Aggregate per-metric pass rates from the JSONB test_metrics column.
    Uses a lightweight Python loop over only the JSON column — the view has
    already performed all joins so no ORM objects are loaded."""
    results = base_q.with_entities(V.test_metrics).all()
    P, F = TestResultStatus.PASSED, TestResultStatus.FAILED
    metric_agg: dict = {}
    for (metrics_json,) in results:
        if not metrics_json or not isinstance(metrics_json, dict):
            continue
        metrics = metrics_json.get("metrics")
        if not isinstance(metrics, dict):
            continue
        for name, data in metrics.items():
            if not isinstance(data, dict) or "is_successful" not in data:
                continue
            if name not in metric_agg:
                metric_agg[name] = {P: 0, F: 0}
            if data["is_successful"]:
                metric_agg[name][P] += 1
            else:
                metric_agg[name][F] += 1
    return build_pass_rate_stats(metric_agg)


def get_test_result_stats(
    db: Session,
    organization_id: str | None = None,
    months: int = 6,
    test_run_id: str | None = None,
    mode: str = "all",
    test_set_ids: List[str] | None = None,
    behavior_ids: List[str] | None = None,
    category_ids: List[str] | None = None,
    topic_ids: List[str] | None = None,
    status_ids: List[str] | None = None,
    test_ids: List[str] | None = None,
    test_type_ids: List[str] | None = None,
    test_run_ids: List[str] | None = None,
    user_ids: List[str] | None = None,
    assignee_ids: List[str] | None = None,
    owner_ids: List[str] | None = None,
    prompt_ids: List[str] | None = None,
    priority_min: int | None = None,
    priority_max: int | None = None,
    tags: List[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> Dict:
    """Get test result statistics. Signature kept identical for backward compatibility."""

    start_date_obj, end_date_obj = parse_date_range(start_date, end_date, months)

    filter_params = {
        "organization_id": organization_id,
        "test_run_id": test_run_id,
        "test_run_ids": test_run_ids,
        "start_date_obj": start_date_obj,
        "end_date_obj": end_date_obj,
        "test_set_ids": test_set_ids,
        "behavior_ids": behavior_ids,
        "category_ids": category_ids,
        "topic_ids": topic_ids,
        "status_ids": status_ids,
        "test_ids": test_ids,
        "test_type_ids": test_type_ids,
        "user_ids": user_ids,
        "assignee_ids": assignee_ids,
        "owner_ids": owner_ids,
        "prompt_ids": prompt_ids,
        "priority_min": priority_min,
        "priority_max": priority_max,
        "tags": tags,
    }

    base_q = _apply_filters(db.query(V), db, **filter_params)

    overall_pass_rates = {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0}
    metric_pass_rates: dict = {}
    behavior_pass_rates: dict = {}
    category_pass_rates: dict = {}
    topic_pass_rates: dict = {}
    timeline: list = []
    test_run_summary: list = []

    if mode in ("all", "overall", "summary"):
        overall_pass_rates = _overall_stats(db, base_q)
    if mode in ("all", "metrics"):
        metric_pass_rates = _metric_stats(base_q)
    if mode in ("all", "behavior"):
        behavior_pass_rates = _dimensional_stats(base_q, V.behavior_name)
    if mode in ("all", "category"):
        category_pass_rates = _dimensional_stats(base_q, V.category_name)
    if mode in ("all", "topic"):
        topic_pass_rates = _dimensional_stats(base_q, V.topic_name)
    if mode in ("all", "timeline"):
        timeline = _timeline_stats(base_q)
    if mode in ("all", "test_runs"):
        test_run_summary = _test_run_summary(base_q)

    total_tests = overall_pass_rates.get("total", 0)
    metadata = {
        "generated_at": datetime.utcnow().isoformat(),
        "organization_id": organization_id,
        "test_run_id": test_run_id,
        "period": f"Last {months} months",
        "start_date": start_date_obj.isoformat() if start_date_obj else None,
        "end_date": end_date_obj.isoformat() if end_date_obj else None,
        "total_test_runs": len(test_run_summary) if test_run_summary else 0,
        "total_test_results": total_tests,
        "mode": mode,
        "available_metrics": list(metric_pass_rates.keys()) if metric_pass_rates else [],
        "available_behaviors": list(behavior_pass_rates.keys()) if behavior_pass_rates else [],
        "available_categories": list(category_pass_rates.keys()) if category_pass_rates else [],
        "available_topics": list(topic_pass_rates.keys()) if topic_pass_rates else [],
    }

    return build_response_data(
        mode,
        MODE_DEFINITIONS,
        metric_pass_rates=metric_pass_rates,
        behavior_pass_rates=behavior_pass_rates,
        category_pass_rates=category_pass_rates,
        topic_pass_rates=topic_pass_rates,
        overall_pass_rates=overall_pass_rates,
        timeline=timeline,
        test_run_summary=test_run_summary,
        metadata=metadata,
    )
