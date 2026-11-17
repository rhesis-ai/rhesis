"""Which results a report counts, the requirement tree, and the section registry."""

import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from rhesis.backend.app.features import FeatureName
from rhesis.backend.app.services.report.counting import (
    RequirementInfo,
    inconsistent_tests,
    pass_rate,
    pick_counted,
    requirement_tree,
    totals,
)
from rhesis.backend.app.services.report.sections import (
    ReportSection,
    get_report_sections,
    register_report_section,
    reset_report_sections,
)
from rhesis.backend.app.services.report.snapshot import run_hashes, snapshot_hash


def _row(
    test_id, requirement_id=None, verdict="pass", execution="ok", run_id=None, overridden=False
):
    status_id = uuid.uuid4()
    return SimpleNamespace(
        id=uuid.uuid4(),
        test_id=test_id,
        test_run_id=run_id or uuid.uuid4(),
        execution=execution,
        verdict=verdict if execution == "ok" else None,
        status_id=status_id,
        original_status_id=uuid.uuid4() if overridden else None,
        created_at=datetime(2026, 11, 1),
        requirement_id=requirement_id,
    )


def test_pass_rate_ignores_everything_but_pass_and_fail():
    assert pass_rate(3, 1) == 75.0
    assert pass_rate(0, 0) is None


def test_latest_result_per_test_counts():
    test_id = uuid.uuid4()
    old, new = _row(test_id, verdict="fail"), _row(test_id, verdict="pass")
    counted = pick_counted([old, new])
    assert [c.verdict for c in counted] == ["pass"]
    assert counted[0].test_result_id == new.id


def test_overridden_when_reviewed_status_differs():
    counted = pick_counted([_row(uuid.uuid4(), overridden=True), _row(uuid.uuid4())])
    assert sorted(c.overridden for c in counted) == [False, True]


def test_tree_nests_children_and_sorts_lowest_pass_rate_first():
    parent = RequirementInfo(uuid.uuid4(), "Parent", None)
    weak = RequirementInfo(uuid.uuid4(), "Weak", parent.id)
    strong = RequirementInfo(uuid.uuid4(), "Strong", parent.id)
    solo = RequirementInfo(uuid.uuid4(), "Solo", None)
    orphan = RequirementInfo(uuid.uuid4(), "Orphan", uuid.uuid4())  # parent not picked
    untested = RequirementInfo(uuid.uuid4(), "Untested", None)
    rows = [
        _row(uuid.uuid4(), weak.id, "fail"),
        _row(uuid.uuid4(), weak.id, "pass"),
        _row(uuid.uuid4(), strong.id, "pass"),
        _row(uuid.uuid4(), solo.id, execution="error"),
        _row(uuid.uuid4(), orphan.id, "fail"),
    ]
    tree = requirement_tree(
        [parent, weak, strong, solo, orphan, untested],
        pick_counted(rows),
        {weak.id: 2, strong.id: 1, solo.id: 1, orphan.id: 1},
    )
    names = [(r["name"], r["level"]) for r in tree]
    assert names == [
        ("Orphan", 0),
        ("Parent", 0),
        ("Weak", 1),
        ("Strong", 1),
        ("Solo", 0),
        ("Untested", 0),
    ]
    by_name = {r["name"]: r for r in tree}
    assert by_name["Parent"]["tests"] == 3
    assert by_name["Parent"]["pass_rate"] == pytest.approx(66.67)
    assert by_name["Solo"]["coverage"] == "errored_only"
    assert by_name["Untested"]["coverage"] == "no_tests"


def test_totals_count_every_counted_result():
    requirement = RequirementInfo(uuid.uuid4(), "R", None)
    counted = pick_counted(
        [
            _row(uuid.uuid4(), requirement.id, "pass"),
            _row(uuid.uuid4(), None, "fail"),  # no requirement: still in the totals
            _row(uuid.uuid4(), None, "inconclusive"),
        ]
    )
    result = totals(counted, requirement_tree([requirement], counted, {requirement.id: 1}))
    assert (result["results"], result["passed"], result["failed"], result["inconclusive"]) == (
        3,
        1,
        1,
        1,
    )
    assert (result["requirements_tested"], result["requirements_total"]) == (1, 1)


def test_hashes_change_with_any_counted_result():
    run_id = uuid.uuid4()
    counted = pick_counted([_row(uuid.uuid4(), run_id=run_id), _row(uuid.uuid4(), run_id=run_id)])
    frozen = {"title": "Release"}
    assert snapshot_hash(frozen, counted) == snapshot_hash(frozen, list(reversed(counted)))
    flipped = pick_counted([_row(counted[0].test_id, verdict="fail", run_id=run_id)])
    assert snapshot_hash(frozen, counted) != snapshot_hash(frozen, flipped)
    assert set(run_hashes(counted)) == {str(run_id)}


class TestSectionRegistry:
    def setup_method(self):
        reset_report_sections()

    def teardown_method(self):
        reset_report_sections()

    def test_same_section_twice_is_a_no_op(self):
        section = ReportSection("by_impact", FeatureName.AUDIT_LOG, lambda db, ctx: {})
        register_report_section(section)
        register_report_section(section)
        assert get_report_sections() == [section]

    def test_different_section_under_same_key_raises(self):
        register_report_section(ReportSection("k", FeatureName.AUDIT_LOG, lambda db, ctx: 1))
        with pytest.raises(RuntimeError):
            register_report_section(ReportSection("k", FeatureName.AUDIT_LOG, lambda db, ctx: 2))


def test_created_at_order_is_callers_job():
    """pick_counted trusts its input order; the CRUD query sorts oldest first."""
    test_id = uuid.uuid4()
    later = _row(test_id, verdict="pass")
    later.created_at += timedelta(hours=1)
    assert pick_counted([later, _row(test_id, verdict="fail")])[0].verdict == "fail"


class TestResultRules:
    """A test that ran three times: pass, fail, pass (oldest run first)."""

    def setup_method(self):
        self.test_id = uuid.uuid4()
        self.requirement = RequirementInfo(uuid.uuid4(), "Repeated", None)
        self.rows = [
            _row(self.test_id, self.requirement.id, verdict) for verdict in ("pass", "fail", "pass")
        ]

    def test_latest_keeps_the_newest(self):
        assert [c.verdict for c in pick_counted(self.rows, "latest")] == ["pass"]

    def test_all_keeps_every_result(self):
        counted = pick_counted(self.rows, "all")
        tree = requirement_tree([self.requirement], counted, {self.requirement.id: 1})
        assert len(counted) == 3
        assert tree[0]["pass_rate"] == pytest.approx(66.67)

    def test_worst_keeps_the_failure(self):
        assert [c.verdict for c in pick_counted(self.rows, "worst")] == ["fail"]

    def test_worst_prefers_a_judged_result_over_an_error(self):
        rows = [_row(self.test_id, verdict="pass"), _row(self.test_id, execution="error")]
        assert [c.verdict for c in pick_counted(rows, "worst")] == ["pass"]

    def test_inconsistent_tests_are_counted_per_requirement(self):
        steady = uuid.uuid4()
        rows = [*self.rows, _row(steady, self.requirement.id, "pass")]
        rows.append(_row(steady, self.requirement.id, "pass"))
        flaky = inconsistent_tests(rows)
        assert flaky == {self.test_id}
        counted = pick_counted(rows, "all")
        tree = requirement_tree([self.requirement], counted, {self.requirement.id: 2}, flaky)
        assert tree[0]["inconsistent"] == 1
        assert totals(counted, tree, flaky)["inconsistent"] == 1

    def test_an_errored_run_is_not_inconsistent(self):
        rows = [_row(self.test_id, verdict="pass"), _row(self.test_id, execution="error")]
        assert inconsistent_tests(rows) == set()


def test_metric_kind_from_type_and_model():
    from rhesis.backend.app.services.report.metric_results import kind_of

    assert kind_of("custom-code", None) == "code"
    assert kind_of("custom-prompt", "jev") == "jev"
    assert kind_of("custom-prompt", "openai") == "llm"
    assert kind_of("framework", None) == "llm"
