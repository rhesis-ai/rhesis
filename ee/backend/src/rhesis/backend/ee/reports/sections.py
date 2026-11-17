"""The Enterprise report sections: by impact, who was involved, stats.

Each is a :class:`ReportSection` builder: it reads what the report counts and returns
JSON, which core shows live for a draft and freezes at publish.
"""

import math
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.services.report.counting import pass_rate
from rhesis.backend.app.services.report.sections import ReportContext
from rhesis.backend.ee.reports import queries

# The seeded RequirementImpact order. type_lookup has no rank column, so impacts a
# project adds come after these by name, and "Not set" comes last.
SEEDED_IMPACT_ORDER = (
    "Safety",
    "Legal & compliance",
    "Privacy & security",
    "Financial",
    "Reputation",
    "Customer experience",
)
NOT_SET = "Not set"


def _impact_sort_key(name: str) -> tuple:
    if name == NOT_SET:
        return (2, 0, "")
    if name in SEEDED_IMPACT_ORDER:
        return (0, SEEDED_IMPACT_ORDER.index(name), "")
    return (1, 0, name.lower())


def _empty_group(impact_id: Optional[uuid.UUID], name: str) -> Dict[str, Any]:
    return {
        "id": str(impact_id) if impact_id else None,
        "name": name,
        "requirements": set(),
        "tested": set(),
        "tests": 0,
        "passed": 0,
        "failed": 0,
        "errored": 0,
    }


def build_by_impact(db: Session, context: ReportContext) -> Dict[str, Any]:
    """Pass rate per impact, over the picked requirements' own results.

    ``requirements`` maps every picked requirement to its impact name, for the impact
    column in the tree. ``impacts`` lists only impacts with a tested requirement.
    """
    impacts = queries.requirement_impacts(db, context.requirement_ids)
    groups: Dict[str, Dict[str, Any]] = {}
    for req_id, (impact_id, name) in impacts.items():
        label = name or NOT_SET
        group = groups.setdefault(label, _empty_group(impact_id, label))
        group["requirements"].add(req_id)

    for result in context.counted:
        if result.requirement_id not in impacts:
            continue
        group = groups[impacts[result.requirement_id][1] or NOT_SET]
        group["tested"].add(result.requirement_id)
        group["tests"] += 1
        if result.execution != "ok":
            group["errored"] += 1
        elif result.verdict == "pass":
            group["passed"] += 1
        elif result.verdict == "fail":
            group["failed"] += 1

    rows = [
        {
            "id": g["id"],
            "name": g["name"],
            "requirements_tested": len(g["tested"]),
            "requirements_total": len(g["requirements"]),
            "tests": g["tests"],
            "passed": g["passed"],
            "failed": g["failed"],
            "errored": g["errored"],
            "pass_rate": pass_rate(g["passed"], g["failed"]),
        }
        for g in groups.values()
        if g["tested"]
    ]
    return {
        "impacts": sorted(rows, key=lambda row: _impact_sort_key(row["name"])),
        # "all" counts every result, so the PDF heads the column "Results".
        "result_rule": context.report.result_rule,
        "requirements": {str(req_id): (name or NOT_SET) for req_id, (_, name) in impacts.items()},
    }


def _person(user) -> Dict[str, Any]:
    return {"id": str(user.id), "name": user.display_name}


def build_people(db: Session, context: ReportContext) -> Dict[str, Any]:
    """Who wrote the report, ran the tests and reviewed results."""
    report = context.report
    runners = queries.run_executors(db, context.test_run_ids)
    reviewers = queries.result_reviewers(db, [r.test_result_id for r in context.counted])
    by_id = {u.id: u for u in queries.users(db, [report.user_id, *runners, *reviewers])}

    def people(ids: List[uuid.UUID]) -> List[Dict[str, Any]]:
        found = [by_id[i] for i in dict.fromkeys(ids) if i in by_id]
        return sorted((_person(u) for u in found), key=lambda p: p["name"].lower())

    return {
        "author": _person(by_id[report.user_id]) if report.user_id in by_id else None,
        "ran_tests": people(runners),
        "reviewers": people(reviewers),
        "verdicts_changed": sum(1 for r in context.counted if r.overridden),
    }


def _percentile(sorted_values: List[float], fraction: float) -> float:
    index = max(0, math.ceil(fraction * len(sorted_values)) - 1)
    return sorted_values[index]


def build_stats(db: Session, context: ReportContext) -> Dict[str, Any]:
    """Result counts and response times. Tokens and cost come later, from traces."""
    judged = sum(1 for r in context.counted if r.execution == "ok")
    times = sorted(queries.execution_times_ms(db, [r.test_result_id for r in context.counted]))
    return {
        "results_judged": judged,
        "results_errored": len(context.counted) - judged,
        "response_time_ms": {
            "mean": round(sum(times) / len(times), 1),
            "p95": round(_percentile(times, 0.95), 1),
            "measured": len(times),
        }
        if times
        else None,
    }
