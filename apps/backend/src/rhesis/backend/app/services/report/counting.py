"""Which results count, and the numbers a report shows. Pure functions over plain rows.

When a test ran in several picked runs, the report's rule decides what counts:

- ``latest``: one result per test, from the most recent run.
- ``all``: every result in every run, so pass rates are averages over repeated runs.
- ``worst``: one result per test, its worst verdict (fail, then inconclusive, then
  pass); an errored result counts only when no run judged the test.

Under ``all`` and ``worst`` a test whose verdict differed between runs is
inconsistent. Pass rate is pass / (pass + fail), as in Insights: inconclusive,
errored and unrun results don't move it.
"""

import uuid
from dataclasses import dataclass, field
from typing import AbstractSet, Any, Dict, Iterable, List, Optional, Set

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
    description: Optional[str] = None


@dataclass
class Tally:
    """Counts of one group of counted results: a requirement, or anything grouped like one."""

    tests: int = 0
    passed: int = 0
    failed: int = 0
    inconclusive: int = 0
    errored: int = 0
    inconsistent: Set[uuid.UUID] = field(default_factory=set)
    # Distinct tests behind the results: under "all" one test counts once per run.
    test_ids: Set[uuid.UUID] = field(default_factory=set)

    def add(self, result: CountedResult) -> None:
        self.tests += 1
        self.test_ids.add(result.test_id)
        if result.execution != Execution.OK.value:
            self.errored += 1
        elif result.verdict == Verdict.PASS.value:
            self.passed += 1
        elif result.verdict == Verdict.FAIL.value:
            self.failed += 1
        else:
            self.inconclusive += 1

    def merge(self, other: "Tally") -> None:
        self.tests += other.tests
        self.passed += other.passed
        self.failed += other.failed
        self.inconclusive += other.inconclusive
        self.errored += other.errored
        self.inconsistent |= other.inconsistent
        self.test_ids |= other.test_ids


def pass_rate(passed: int, failed: int) -> Optional[float]:
    judged = passed + failed
    return round(passed * 100 / judged, 2) if judged else None


def _counted(row: Any) -> CountedResult:
    return CountedResult(
        test_result_id=row.id,
        test_id=row.test_id,
        test_run_id=row.test_run_id,
        requirement_id=row.requirement_id,
        execution=row.execution,
        verdict=row.verdict,
        overridden=row.original_status_id is not None and row.original_status_id != row.status_id,
    )


# Worst first: higher is worse. Errored ranks lowest, so a judged result wins.
_SEVERITY = {Verdict.FAIL.value: 3, Verdict.INCONCLUSIVE.value: 2, Verdict.PASS.value: 1}


def _severity(row: Any) -> int:
    if row.execution != Execution.OK.value:
        return 0
    return _SEVERITY.get(row.verdict, 2)


def pick_counted(rows: Iterable[Any], rule: str = "latest") -> List[CountedResult]:
    """The results the report counts under ``rule``. ``rows`` must come oldest run first."""
    rows = list(rows)
    if rule == "all":
        return [_counted(row) for row in rows]
    chosen: Dict[uuid.UUID, Any] = {}
    for row in rows:
        current = chosen.get(row.test_id)
        # Ties go to the later run, so "worst" still prefers recent evidence.
        if rule != "worst" or current is None or _severity(row) >= _severity(current):
            chosen[row.test_id] = row
    return [_counted(row) for row in chosen.values()]


def inconsistent_tests(rows: Iterable[Any]) -> Set[uuid.UUID]:
    """Tests judged differently in different runs (errored runs don't count)."""
    verdicts: Dict[uuid.UUID, Set[str]] = {}
    for row in rows:
        if row.execution == Execution.OK.value and row.verdict:
            verdicts.setdefault(row.test_id, set()).add(row.verdict)
    return {test_id for test_id, seen in verdicts.items() if len(seen) > 1}


def coverage(tally: Tally, has_tests: bool) -> str:
    if tally.tests == 0:
        return "not_in_runs" if has_tests else "no_tests"
    if tally.errored == tally.tests:
        return "errored_only"
    return "tested"


def _row(info: RequirementInfo, level: int, tally: Tally, has_tests: bool) -> dict:
    return {
        "id": info.id,
        "name": info.name,
        "description": info.description,
        "parent_id": info.parent_id,
        "level": level,
        "coverage": coverage(tally, has_tests),
        "tests": tally.tests,
        "distinct_tests": len(tally.test_ids),
        "passed": tally.passed,
        "failed": tally.failed,
        "errored": tally.errored,
        "pass_rate": pass_rate(tally.passed, tally.failed),
        "inconsistent": len(tally.inconsistent),
    }


def _sort_key(row: dict) -> tuple:
    # Lowest pass rate first; untested last.
    rate = row["pass_rate"]
    return (rate is None, rate if rate is not None else 0.0, row["name"].lower())


def requirement_tree(
    requirements: List[RequirementInfo],
    counted: List[CountedResult],
    tests_by_requirement: Dict[uuid.UUID, int],
    inconsistent: AbstractSet[uuid.UUID] = frozenset(),
) -> List[dict]:
    """Picked requirements as parent rows with their picked children indented below.

    A parent adds up its own results and its children's. A requirement whose parent
    isn't picked shows at the top level.
    """
    own: Dict[uuid.UUID, Tally] = {r.id: Tally() for r in requirements}
    for result in counted:
        if result.requirement_id in own:
            own[result.requirement_id].add(result)
            if result.test_id in inconsistent:
                own[result.requirement_id].inconsistent.add(result.test_id)

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
        tally = Tally()
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


def totals(
    counted: List[CountedResult],
    tree: List[dict],
    inconsistent: AbstractSet[uuid.UUID] = frozenset(),
) -> dict:
    tally = Tally()
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
        "inconsistent": len(inconsistent),
    }
