"""The Enterprise report sections: by impact, who was involved, stats.

Each is a :class:`ReportSection` builder: it reads what the report counts and returns
JSON, which core shows live for a draft and freezes at publish.
"""

import math
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.outcomes import Execution
from rhesis.backend.app.services.report.counting import Tally, coverage, pass_rate
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


def build_by_impact(db: Session, context: ReportContext) -> Dict[str, Any]:
    """Pass rate per impact, over the picked requirements' own results.

    Counts with core's Tally and coverage rule, so "requirements tested" agrees with
    the headline number. ``requirements`` maps every picked requirement to its impact
    name, for the impact column in the tree. ``impacts`` lists only impacts with a
    tested requirement.
    """
    impacts = queries.requirement_impacts(db, context.requirement_ids)
    own: Dict[uuid.UUID, Tally] = {req_id: Tally() for req_id in impacts}
    for result in context.counted:
        if result.requirement_id in own:
            own[result.requirement_id].add(result)

    groups: Dict[str, Dict[str, Any]] = {}
    for req_id, (impact_id, name) in impacts.items():
        label = name or NOT_SET
        group = groups.setdefault(
            label,
            {
                "id": str(impact_id) if impact_id else None,
                "name": label,
                "tally": Tally(),
                "total": 0,
                "tested": 0,
            },
        )
        group["total"] += 1
        group["tally"].merge(own[req_id])
        if coverage(own[req_id], has_tests=True) == "tested":
            group["tested"] += 1

    rows = [
        {
            "id": g["id"],
            "name": g["name"],
            "requirements_tested": g["tested"],
            "requirements_total": g["total"],
            "tests": g["tally"].tests,
            "passed": g["tally"].passed,
            "failed": g["tally"].failed,
            "errored": g["tally"].errored,
            "pass_rate": pass_rate(g["tally"].passed, g["tally"].failed),
        }
        for g in groups.values()
        if g["tested"]
    ]
    return {
        "impacts": sorted(rows, key=lambda row: _impact_sort_key(row["name"])),
        # "all" counts every result, so the PDF heads the column "Results".
        "result_rule": context.report.result_rule,
        # Whether the requirements table has a Change column to line up with.
        "compared": context.report.baseline_report_id is not None,
        "requirements": {str(req_id): (name or NOT_SET) for req_id, (_, name) in impacts.items()},
    }


def _person(user) -> Dict[str, Any]:
    return {"id": str(user.id), "name": user.display_name}


def build_people(db: Session, context: ReportContext) -> Optional[Dict[str, Any]]:
    """Who wrote the report, ran the tests and reviewed results. Release reports only."""
    report = context.report
    if not report.is_release:
        return None
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
    judged = sum(1 for r in context.counted if r.execution == Execution.OK.value)
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
