"""Which results count, and the numbers a report shows. Pure functions over plain rows.

When a test ran in several picked runs, the latest result counts. Pass rate is
pass / (pass + fail), as in Insights: inconclusive, errored and unrun results don't
move it.
"""

import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from rhesis.backend.app.outcomes import Execution, Verdict


@dataclass(frozen=True)
class CountedResult:
    test_result_id: uuid.UUID
    test_id: uuid.UUID
    test_run_id: uuid.UUID
    requirement_id: Optional[uuid.UUID]
    execution: str
    verdict: Optional[str]
    overridden: bool


@dataclass(frozen=True)
class RequirementInfo:
    id: uuid.UUID
    name: str
    parent_id: Optional[uuid.UUID]


@dataclass
class _Tally:
    tests: int = 0
    passed: int = 0
    failed: int = 0
    inconclusive: int = 0
    errored: int = 0

    def add(self, result: CountedResult) -> None:
        self.tests += 1
        if result.execution != Execution.OK.value:
            self.errored += 1
        elif result.verdict == Verdict.PASS.value:
            self.passed += 1
        elif result.verdict == Verdict.FAIL.value:
            self.failed += 1
        else:
            self.inconclusive += 1

    def merge(self, other: "_Tally") -> None:
        self.tests += other.tests
        self.passed += other.passed
        self.failed += other.failed
        self.inconclusive += other.inconclusive
        self.errored += other.errored


def pass_rate(passed: int, failed: int) -> Optional[float]:
    judged = passed + failed
    return round(passed * 100 / judged, 2) if judged else None


def pick_counted(rows: Iterable[Any]) -> List[CountedResult]:
    """One result per test: the latest. ``rows`` must come oldest first."""
    latest: Dict[uuid.UUID, Any] = {}
    for row in rows:
        latest[row.test_id] = row
    return [
        CountedResult(
            test_result_id=row.id,
            test_id=row.test_id,
            test_run_id=row.test_run_id,
            requirement_id=row.requirement_id,
            execution=row.execution,
            verdict=row.verdict,
            overridden=row.original_status_id is not None
            and row.original_status_id != row.status_id,
        )
        for row in latest.values()
    ]


def _coverage(tally: _Tally, has_tests: bool) -> str:
    if tally.tests == 0:
        return "not_in_runs" if has_tests else "no_tests"
    if tally.errored == tally.tests:
        return "errored_only"
    return "tested"


def _row(info: RequirementInfo, level: int, tally: _Tally, has_tests: bool) -> dict:
    return {
        "id": info.id,
        "name": info.name,
        "parent_id": info.parent_id,
        "level": level,
        "coverage": _coverage(tally, has_tests),
        "tests": tally.tests,
        "passed": tally.passed,
        "failed": tally.failed,
        "errored": tally.errored,
        "pass_rate": pass_rate(tally.passed, tally.failed),
    }


def _sort_key(row: dict) -> tuple:
    # Lowest pass rate first; untested last.
    rate = row["pass_rate"]
    return (rate is None, rate if rate is not None else 0.0, row["name"].lower())


def requirement_tree(
    requirements: List[RequirementInfo],
    counted: List[CountedResult],
    tests_by_requirement: Dict[uuid.UUID, int],
) -> List[dict]:
    """Picked requirements as parent rows with their picked children indented below.

    A parent adds up its own results and its children's. A requirement whose parent
    isn't picked shows at the top level.
    """
    own: Dict[uuid.UUID, _Tally] = {r.id: _Tally() for r in requirements}
    for result in counted:
        if result.requirement_id in own:
            own[result.requirement_id].add(result)

    picked = {r.id for r in requirements}
    children: Dict[uuid.UUID, List[RequirementInfo]] = {}
    tops: List[RequirementInfo] = []
    for r in requirements:
        if r.parent_id in picked:
            children.setdefault(r.parent_id, []).append(r)
        else:
            tops.append(r)

    rows: List[dict] = []
    top_rows = []
    for top in tops:
        child_rows = [
            _row(c, 1, own[c.id], tests_by_requirement.get(c.id, 0) > 0)
            for c in children.get(top.id, [])
        ]
        tally = _Tally()
        tally.merge(own[top.id])
        for c in children.get(top.id, []):
            tally.merge(own[c.id])
        has_tests = tests_by_requirement.get(top.id, 0) > 0 or any(
            tests_by_requirement.get(c.id, 0) > 0 for c in children.get(top.id, [])
        )
        top_rows.append((_row(top, 0, tally, has_tests), sorted(child_rows, key=_sort_key)))
    for top_row, child_rows in sorted(top_rows, key=lambda pair: _sort_key(pair[0])):
        rows.append(top_row)
        rows.extend(child_rows)
    return rows


def totals(counted: List[CountedResult], tree: List[dict]) -> dict:
    tally = _Tally()
    for result in counted:
        tally.add(result)
    return {
        "results": tally.tests,
        "passed": tally.passed,
        "failed": tally.failed,
        "inconclusive": tally.inconclusive,
        "errored": tally.errored,
        "pass_rate": pass_rate(tally.passed, tally.failed),
        "requirements_tested": sum(1 for row in tree if row["coverage"] == "tested"),
        "requirements_total": len(tree),
    }
