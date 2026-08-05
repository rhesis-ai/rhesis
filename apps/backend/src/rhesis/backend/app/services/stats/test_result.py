"""Test result statistics using the v_test_result_stats database view."""

from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from rhesis.backend.app.constants import OverallTestResult
from rhesis.backend.app.models.stats_views import MetricStatsView, TestResultStatsView

from .common import (
    build_metric_pass_rate_stats,
    build_pass_rate_stats,
    build_response_data,
    parse_date_range,
)

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
    "timeline": ["timeline"],
    "test_runs": ["test_run_summary"],
    "summary": ["overall_pass_rates"],
    "ids": ["test_ids"],
    "behavior_detail": ["behavior_detail"],
}

V = TestResultStatsView
M = MetricStatsView


def _metric_base(db, base_q):
    """Scope v_metric_stats down to the test_results matched by base_q's filters.

    Reuses _apply_filters' output instead of re-implementing it against M, so
    metric stats stay consistent with every other breakdown by construction.
    """
    matching_ids = base_q.with_entities(V.test_result_id)
    return db.query(M).filter(M.test_result_id.in_(matching_ids))


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

    if f.get("topic_name"):
        query = query.filter(func.lower(V.topic_name) == f["topic_name"].lower())

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
        func.count().filter(V.result == OverallTestResult.PASSED).label("passed"),
        func.count().filter(V.result == OverallTestResult.FAILED).label("failed"),
        func.count().filter(V.result == OverallTestResult.PENDING).label("pending"),
    ).one()
    passed = r.passed or 0
    failed = r.failed or 0
    pending = r.pending or 0
    total = passed + failed  # Calculate pass_rate based only on completed runs
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pending": pending,
        "pass_rate": round((passed / total) * 100, 2) if total > 0 else 0,
    }


def _timeline_stats(db, base_q):
    """Monthly pass/fail trend, with a per-metric breakdown, both via SQL GROUP BY."""
    overall_q = (
        base_q.filter(V.year.isnot(None))
        .with_entities(
            V.year,
            V.month,
            func.count().filter(V.result == OverallTestResult.PASSED).label("passed"),
            func.count().filter(V.result == OverallTestResult.FAILED).label("failed"),
        )
        .group_by(V.year, V.month)
    )
    overall_by_month = {(r.year, r.month): (r.passed or 0, r.failed or 0) for r in overall_q.all()}

    metric_q = (
        _metric_base(db, base_q)
        .filter(M.year.isnot(None))
        .with_entities(
            M.year,
            M.month,
            M.metric_name,
            func.count().filter(M.effective_success.is_(True)).label("passed"),
            func.count().filter(M.effective_success.is_(False)).label("failed"),
        )
        .group_by(M.year, M.month, M.metric_name)
    )
    metrics_by_month: dict = {}
    for r in metric_q.all():
        bucket = metrics_by_month.setdefault((r.year, r.month), {})
        bucket[r.metric_name] = {"passed": r.passed or 0, "failed": r.failed or 0}

    timeline = []
    for year, month in sorted(set(overall_by_month) | set(metrics_by_month)):
        passed, failed = overall_by_month.get((year, month), (0, 0))
        total = passed + failed
        timeline.append(
            {
                "date": f"{year:04d}-{month:02d}",
                "overall": {
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "pass_rate": round((passed / total) * 100, 2) if total > 0 else 0,
                },
                "metrics": build_pass_rate_stats(metrics_by_month.get((year, month), {})),
            }
        )
    return timeline


def _dimensional_stats(base_q, name_col):
    """Pass rate grouped by a pre-joined name column (behavior_name, category_name, topic_name)."""
    q = base_q.with_entities(
        name_col.label("name"),
        func.count().filter(V.result == OverallTestResult.PASSED).label("passed"),
        func.count().filter(V.result == OverallTestResult.FAILED).label("failed"),
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
            func.count().filter(V.result == OverallTestResult.PASSED).label("passed"),
            func.count().filter(V.result == OverallTestResult.FAILED).label("failed"),
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


def _metric_stats(db, base_q):
    """Aggregate per-metric pass rates via SQL GROUP BY on v_metric_stats."""
    q = (
        _metric_base(db, base_q)
        .with_entities(
            M.metric_name,
            func.count().filter(M.effective_success.is_(True)).label("passed"),
            func.count().filter(M.effective_success.is_(False)).label("failed"),
            func.count().filter(M.automated_success.is_(True)).label("automated_passed"),
            func.count().filter(M.automated_success.is_(False)).label("automated_failed"),
            func.count().filter(M.has_override.is_(True)).label("human_review_count"),
        )
        .group_by(M.metric_name)
    )
    normalized = {
        r.metric_name: {
            "passed": r.passed or 0,
            "failed": r.failed or 0,
            "automated_passed": r.automated_passed or 0,
            "automated_failed": r.automated_failed or 0,
            "human_review_count": r.human_review_count or 0,
        }
        for r in q.all()
    }
    return build_metric_pass_rate_stats(normalized)


def _behavior_overall_stats(base_q) -> Dict[str, Dict]:
    """Overall pass/fail counts grouped by behavior_id, in one query."""
    q = base_q.with_entities(
        V.behavior_id,
        func.count().filter(V.result == OverallTestResult.PASSED).label("passed"),
        func.count().filter(V.result == OverallTestResult.FAILED).label("failed"),
    ).group_by(V.behavior_id)

    result = {}
    for r in q.all():
        if r.behavior_id is None:
            continue
        passed, failed = r.passed or 0, r.failed or 0
        total = passed + failed
        result[str(r.behavior_id)] = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round((passed / total) * 100, 2) if total > 0 else 0,
        }
    return result


def _behavior_dimensional_stats(base_q, name_col) -> Dict[str, Dict]:
    """Pass rate grouped by behavior_id + a name column (e.g. topic_name), in one query."""
    q = base_q.with_entities(
        V.behavior_id,
        name_col.label("name"),
        func.count().filter(V.result == OverallTestResult.PASSED).label("passed"),
        func.count().filter(V.result == OverallTestResult.FAILED).label("failed"),
    ).group_by(V.behavior_id, name_col)

    grouped: Dict[str, dict] = {}
    for r in q.all():
        if r.behavior_id is None:
            continue
        bid = str(r.behavior_id)
        grouped.setdefault(bid, {})[r.name or "Unknown"] = {
            "passed": r.passed or 0,
            "failed": r.failed or 0,
        }
    return {bid: build_pass_rate_stats(stats) for bid, stats in grouped.items()}


def _behavior_metric_stats(db, base_q) -> Dict[str, Dict]:
    """Per-metric pass rates grouped by behavior_id, via SQL GROUP BY on v_metric_stats."""
    q = (
        _metric_base(db, base_q)
        .filter(M.behavior_id.isnot(None))
        .with_entities(
            M.behavior_id,
            M.metric_name,
            func.count().filter(M.effective_success.is_(True)).label("passed"),
            func.count().filter(M.effective_success.is_(False)).label("failed"),
            func.count().filter(M.automated_success.is_(True)).label("automated_passed"),
            func.count().filter(M.automated_success.is_(False)).label("automated_failed"),
            func.count().filter(M.has_override.is_(True)).label("human_review_count"),
        )
        .group_by(M.behavior_id, M.metric_name)
    )
    per_behavior: Dict[str, dict] = {}
    for r in q.all():
        per_behavior.setdefault(str(r.behavior_id), {})[r.metric_name] = {
            "passed": r.passed or 0,
            "failed": r.failed or 0,
            "automated_passed": r.automated_passed or 0,
            "automated_failed": r.automated_failed or 0,
            "human_review_count": r.human_review_count or 0,
        }
    return {bid: build_metric_pass_rate_stats(stats) for bid, stats in per_behavior.items()}


def _behavior_breakdown(db, base_q) -> Dict[str, Dict]:
    """Per-behavior overall/metric/topic pass rates in 3 queries total,
    regardless of how many behavior_ids are requested."""
    overall = _behavior_overall_stats(base_q)
    metrics = _behavior_metric_stats(db, base_q)
    topics = _behavior_dimensional_stats(base_q, V.topic_name)
    empty_overall = {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0}

    return {
        bid: {
            "overall_pass_rates": overall.get(bid, empty_overall),
            "metric_pass_rates": metrics.get(bid, {}),
            "topic_pass_rates": topics.get(bid, {}),
        }
        for bid in set(overall) | set(metrics) | set(topics)
    }


def _test_ids_by_metric(db, base_q, metric_name: str, outcome: str) -> List[str]:
    """Return distinct test_ids where a specific metric matches the requested
    outcome ('pass', 'fail', or 'all'), via a direct filter on v_metric_stats."""
    q = (
        _metric_base(db, base_q)
        .filter(M.metric_name == metric_name)
        .with_entities(M.test_id)
        .distinct()
    )
    if outcome != "all":
        q = q.filter(M.effective_success.is_(outcome == "pass"))
    return [row.test_id for row in q.all()]


def _test_ids_overall(base_q, outcome: str) -> List[str]:
    """Return distinct test_ids matching the requested overall outcome
    ('pass', 'fail', or 'all'), without narrowing to a specific metric."""
    q = base_q.with_entities(V.test_id).distinct()
    if outcome == "pass":
        q = q.filter(V.result == OverallTestResult.PASSED)
    elif outcome == "fail":
        q = q.filter(V.result == OverallTestResult.FAILED)
    return [row.test_id for row in q.all()]


def get_test_result_stats(
    db: Session,
    organization_id: str | None = None,
    months: int | None = None,
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
    metric_name: str | None = None,
    outcome: str = "all",
    topic_name: str | None = None,
) -> Dict:
    """Get test result statistics. Signature kept identical for backward compatibility.

    metric_name/outcome/topic_name are only used by mode="ids": metric_name
    narrows to one metric's pass/fail outcome; without it, outcome applies to
    the overall test result instead. topic_name further narrows by topic.
    """

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
        "topic_name": topic_name,
    }

    base_q = _apply_filters(db.query(V), db, **filter_params)

    overall_pass_rates = {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0}
    metric_pass_rates: dict = {}
    behavior_pass_rates: dict = {}
    category_pass_rates: dict = {}
    topic_pass_rates: dict = {}
    timeline: list = []
    test_run_summary: list = []
    matched_test_ids: list = []
    behavior_detail: dict = {}

    if mode == "ids":
        matched_test_ids = (
            _test_ids_by_metric(db, base_q, metric_name, outcome)
            if metric_name
            else _test_ids_overall(base_q, outcome)
        )
    if mode == "behavior_detail":
        behavior_detail = _behavior_breakdown(db, base_q)
    if mode in ("all", "summary", "behavior_detail"):
        overall_pass_rates = _overall_stats(db, base_q)
    if mode in ("all", "metrics"):
        metric_pass_rates = _metric_stats(db, base_q)
    if mode in ("all", "behavior"):
        behavior_pass_rates = _dimensional_stats(base_q, V.behavior_name)
    if mode in ("all", "category"):
        category_pass_rates = _dimensional_stats(base_q, V.category_name)
    if mode in ("all", "topic"):
        topic_pass_rates = _dimensional_stats(base_q, V.topic_name)
    if mode in ("all", "timeline"):
        timeline = _timeline_stats(db, base_q)
    if mode in ("all", "test_runs"):
        test_run_summary = _test_run_summary(base_q)

    total_tests = len(matched_test_ids) if mode == "ids" else overall_pass_rates.get("total", 0)
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "organization_id": organization_id,
        "test_run_id": test_run_id,
        "period": f"Last {months} months" if months is not None else "all time",
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
        test_ids=[str(tid) for tid in matched_test_ids],
        behavior_detail=behavior_detail,
        metadata=metadata,
    )
