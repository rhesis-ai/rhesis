"""Integration coverage for the verdict matrix: build_metric_plan's
dispatch-time snapshot feeding get_verdict_matrix's encoded grid, against a
real Postgres so v_metric_stats/v_test_result_stats are exercised for real.

The riskiest part of this feature is that a metric plan's row key must match
the JSONB key v_metric_stats reports for that metric's result -- both derive
the key the same way (name/class_name/id, suffixed on collision), but they
run in different modules (jobs/execution/metric_plan.py vs
metrics/strategies/local.py) at different times, so a drift between them
would silently blank every cell instead of raising.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.constants import TestResultStatus
from rhesis.backend.app.services.test_run import get_verdict_matrix
from rhesis.backend.app.utils.crud_utils import get_or_create_status, get_or_create_type_lookup
from rhesis.backend.jobs.execution.metric_plan import build_metric_plan


def _metric(db, org_id, user_id, *, name, scope, class_name="AccuracyMetric"):
    backend_type = get_or_create_type_lookup(db, "BackendType", "rhesis", str(org_id), str(user_id))
    metric_type = get_or_create_type_lookup(
        db, "MetricType", "custom-prompt", str(org_id), str(user_id)
    )
    metric = models.Metric(
        metric_scope=scope,
        name=name,
        class_name=class_name,
        score_type="numeric",
        evaluation_prompt="Evaluate",
        backend_type_id=backend_type.id,
        metric_type_id=metric_type.id,
        organization_id=org_id,
        user_id=user_id,
    )
    db.add(metric)
    db.flush()
    return metric


def _link_metric(db, requirement, metric, org_id, user_id):
    db.execute(
        models.requirement_metric_association.insert().values(
            requirement_id=requirement.id,
            metric_id=metric.id,
            organization_id=org_id,
            user_id=user_id,
        )
    )


def _add_to_set(db, test, test_set, org_id, user_id):
    db.execute(
        models.test_test_set_association.insert().values(
            test_id=test.id,
            test_set_id=test_set.id,
            organization_id=org_id,
            user_id=user_id,
        )
    )


@pytest.fixture
def verdict_matrix_setup(test_db: Session, test_organization, db_user, db_endpoint, db_status):
    org_id = test_organization.id
    user_id = db_user.id

    test_config = models.TestConfiguration(
        endpoint_id=db_endpoint.id,
        organization_id=org_id,
        user_id=user_id,
    )
    test_db.add(test_config)
    test_db.flush()

    test_set = models.TestSet(
        name="Verdict Matrix Test Set",
        user_id=user_id,
        organization_id=org_id,
        status_id=db_status.id,
    )
    test_db.add(test_set)
    test_db.flush()
    test_config.test_set_id = test_set.id
    test_db.flush()

    requirement = models.Requirement(
        name="Req A",
        organization_id=org_id,
        user_id=user_id,
    )
    test_db.add(requirement)
    test_db.flush()

    backend_type = get_or_create_type_lookup(
        test_db, "BackendType", "rhesis", str(org_id), str(user_id)
    )
    metric_type = get_or_create_type_lookup(
        test_db, "MetricType", "custom-prompt", str(org_id), str(user_id)
    )

    metric = models.Metric(
        metric_scope=["Single-Turn"],
        name="Accuracy",
        class_name="AccuracyMetric",
        score_type="numeric",
        evaluation_prompt="Evaluate accuracy",
        backend_type_id=backend_type.id,
        metric_type_id=metric_type.id,
        organization_id=org_id,
        user_id=user_id,
    )
    test_db.add(metric)
    test_db.flush()

    test_db.execute(
        models.requirement_metric_association.insert().values(
            requirement_id=requirement.id,
            metric_id=metric.id,
            organization_id=org_id,
            user_id=user_id,
        )
    )

    test_a = models.Test(user_id=user_id, organization_id=org_id, requirement_id=requirement.id)
    test_b = models.Test(user_id=user_id, organization_id=org_id, requirement_id=requirement.id)
    test_db.add_all([test_a, test_b])
    test_db.flush()

    for test in (test_a, test_b):
        test_db.execute(
            models.test_test_set_association.insert().values(
                test_id=test.id,
                test_set_id=test_set.id,
                organization_id=org_id,
                user_id=user_id,
            )
        )

    test_run = models.TestRun(
        name="Verdict Matrix Run",
        user_id=user_id,
        organization_id=org_id,
        status_id=db_status.id,
        test_configuration_id=test_config.id,
        project_id=None,
    )
    test_db.add(test_run)
    test_db.flush()

    pass_status = get_or_create_status(
        test_db, TestResultStatus.PASS.value, "TestResult", organization_id=str(org_id)
    )

    passed_result = models.TestResult(
        test_run_id=test_run.id,
        test_configuration_id=test_config.id,
        test_id=test_a.id,
        organization_id=org_id,
        user_id=user_id,
        status_id=pass_status.id,
        test_metrics={"metrics": {"Accuracy": {"is_successful": True, "score": 0.95}}},
    )
    test_db.add(passed_result)
    test_db.commit()

    return {
        "test_config": test_config,
        "test_set": test_set,
        "test_run": test_run,
        "requirement": requirement,
        "metric": metric,
        "test_a": test_a,
        "test_b": test_b,
        "org_id": str(org_id),
    }


@pytest.fixture
def two_requirement_setup(test_db: Session, test_organization, db_user, db_endpoint, db_status):
    """Two requirements, one test each, both metrics named "Accuracy".

    The shared name is deliberate: it is what makes a missing group boundary
    visible, since a (test_id, metric_key) lookup with no requirement
    dimension would pull one requirement's verdict onto the other's row.
    """
    org_id = test_organization.id
    user_id = db_user.id

    test_config = models.TestConfiguration(
        endpoint_id=db_endpoint.id, organization_id=org_id, user_id=user_id
    )
    test_db.add(test_config)
    test_db.flush()

    test_set = models.TestSet(
        name="Two Requirement Test Set",
        user_id=user_id,
        organization_id=org_id,
        status_id=db_status.id,
    )
    test_db.add(test_set)
    test_db.flush()
    test_config.test_set_id = test_set.id
    test_db.flush()

    backend_type = get_or_create_type_lookup(
        test_db, "BackendType", "rhesis", str(org_id), str(user_id)
    )
    metric_type = get_or_create_type_lookup(
        test_db, "MetricType", "custom-prompt", str(org_id), str(user_id)
    )

    groups = {}
    for label in ("a", "b"):
        requirement = models.Requirement(
            name=f"Req {label.upper()}", organization_id=org_id, user_id=user_id
        )
        test_db.add(requirement)
        test_db.flush()

        metric = models.Metric(
            metric_scope=["Single-Turn"],
            name="Accuracy",
            class_name="AccuracyMetric",
            score_type="numeric",
            evaluation_prompt="Evaluate accuracy",
            backend_type_id=backend_type.id,
            metric_type_id=metric_type.id,
            organization_id=org_id,
            user_id=user_id,
        )
        test_db.add(metric)
        test_db.flush()
        test_db.execute(
            models.requirement_metric_association.insert().values(
                requirement_id=requirement.id,
                metric_id=metric.id,
                organization_id=org_id,
                user_id=user_id,
            )
        )

        test = models.Test(user_id=user_id, organization_id=org_id, requirement_id=requirement.id)
        test_db.add(test)
        test_db.flush()
        test_db.execute(
            models.test_test_set_association.insert().values(
                test_id=test.id,
                test_set_id=test_set.id,
                organization_id=org_id,
                user_id=user_id,
            )
        )
        groups[label] = {"requirement": requirement, "metric": metric, "test": test}

    test_run = models.TestRun(
        name="Two Requirement Run",
        user_id=user_id,
        organization_id=org_id,
        status_id=db_status.id,
        test_configuration_id=test_config.id,
    )
    test_db.add(test_run)
    test_db.flush()

    # Test A passes its metric, test B fails its own -- distinct verdicts so a
    # row picking up the wrong test's cell is unambiguous in the assertion.
    for label, status_name, is_successful in (
        ("a", TestResultStatus.PASS.value, True),
        ("b", TestResultStatus.FAIL.value, False),
    ):
        status = get_or_create_status(
            test_db, status_name, "TestResult", organization_id=str(org_id)
        )
        test_db.add(
            models.TestResult(
                test_run_id=test_run.id,
                test_configuration_id=test_config.id,
                test_id=groups[label]["test"].id,
                organization_id=org_id,
                user_id=user_id,
                status_id=status.id,
                test_metrics={"metrics": {"Accuracy": {"is_successful": is_successful}}},
            )
        )
    test_db.commit()

    return {
        "test_config": test_config,
        "test_set": test_set,
        "test_run": test_run,
        "requirement_a": groups["a"]["requirement"],
        "requirement_b": groups["b"]["requirement"],
        "test_a": groups["a"]["test"],
        "test_b": groups["b"]["test"],
        "org_id": str(org_id),
    }


class TestBuildMetricPlan:
    def test_requirement_sourced_plan_has_one_row_per_metric(
        self, test_db: Session, verdict_matrix_setup
    ):
        setup = verdict_matrix_setup
        plan = build_metric_plan(
            test_db,
            setup["test_config"],
            setup["test_set"],
            organization_id=setup["org_id"],
        )

        assert plan["source"] == "requirement"
        assert len(plan["requirements"]) == 1
        group = plan["requirements"][0]
        assert group["id"] == str(setup["requirement"].id)
        assert group["name"] == "Req A"
        assert [m["key"] for m in group["metrics"]] == ["Accuracy"]
        assert group["metrics"][0]["ambiguous"] is False

        test_order = plan["test_order"]
        assert set(test_order) == {str(setup["test_a"].id), str(setup["test_b"].id)}

        # Both tests are single-turn and the metric is Single-Turn scoped, so
        # nothing is filtered: every test maps the row to the bare key.
        metric_ref = str(setup["metric"].id)
        assert plan["cell_keys"] == {
            str(setup["test_a"].id): {metric_ref: "Accuracy"},
            str(setup["test_b"].id): {metric_ref: "Accuracy"},
        }
        assert group["test_ids"] == test_order

    def test_restores_request_scope(self, test_db: Session, verdict_matrix_setup):
        """get_test_metrics calls bind_scope_to_session, and this runs inside
        the FastAPI request that dispatches the run -- a leaked _scope would
        apply a stale project filter to every later query on that session.
        """
        setup = verdict_matrix_setup
        before = test_db.info.get("_scope")

        build_metric_plan(
            test_db,
            setup["test_config"],
            setup["test_set"],
            organization_id=setup["org_id"],
        )

        assert test_db.info.get("_scope") == before


class TestGetVerdictMatrix:
    def test_encodes_passed_and_pending_cells(self, test_db: Session, verdict_matrix_setup):
        setup = verdict_matrix_setup
        plan = build_metric_plan(
            test_db,
            setup["test_config"],
            setup["test_set"],
            organization_id=setup["org_id"],
        )
        test_run = setup["test_run"]
        test_run.attributes = {"metric_plan": plan}
        test_db.commit()
        test_db.refresh(test_run)

        matrix = get_verdict_matrix(test_db, test_run)

        assert len(matrix.rows) == 1
        row = matrix.rows[0]
        assert row.metric_key == "Accuracy"

        test_order = plan["test_order"]
        index_a = test_order.index(str(setup["test_a"].id))
        index_b = test_order.index(str(setup["test_b"].id))
        assert row.verdicts[index_a] == "P"
        assert row.verdicts[index_b] == "."
        assert row.passed == 1
        assert row.pending == 1
        assert row.failed == 0

        assert matrix.kpis.tests_total == 2
        assert matrix.kpis.tests_executed == 1
        assert matrix.kpis.verdicts_planned == 2
        assert matrix.kpis.verdicts_resolved == 1
        assert matrix.kpis.failures == 0
        # Over tests (1 of 1 executed passed), not over verdicts -- see the
        # pass_rate comment in get_verdict_matrix.
        assert matrix.kpis.pass_rate == 1.0

    def test_columns_none_omits_test_ids(self, test_db: Session, verdict_matrix_setup):
        setup = verdict_matrix_setup
        plan = build_metric_plan(
            test_db,
            setup["test_config"],
            setup["test_set"],
            organization_id=setup["org_id"],
        )
        test_run = setup["test_run"]
        test_run.attributes = {"metric_plan": plan}
        test_db.commit()
        test_db.refresh(test_run)

        full = get_verdict_matrix(test_db, test_run)
        assert full.test_ids is not None
        assert len(full.test_ids) == 2

        thin = get_verdict_matrix(test_db, test_run, columns="none")
        assert thin.test_ids is None
        assert len(thin.rows) == len(full.rows)

    def test_missing_plan_falls_back_to_recorded_results(
        self, test_db: Session, verdict_matrix_setup
    ):
        """No stored metric_plan (a legacy run) -- the grid is derived from
        v_metric_stats instead of a prospective plan, and still shows the
        one metric that has a recorded verdict.
        """
        setup = verdict_matrix_setup
        test_run = setup["test_run"]
        assert not (test_run.attributes or {}).get("metric_plan")

        matrix = get_verdict_matrix(test_db, test_run)

        assert len(matrix.rows) == 1
        assert matrix.rows[0].metric_key == "Accuracy"
        assert matrix.rows[0].passed == 1


class TestTwoRequirements:
    """A metric row belongs to one requirement, so it must only span that
    requirement's own tests. Everything else in the run is a column the row
    can never have a verdict for and has to read as not-applicable.
    """

    def test_row_marks_other_requirements_tests_not_applicable(
        self, test_db: Session, two_requirement_setup
    ):
        setup = two_requirement_setup
        plan = build_metric_plan(
            test_db,
            setup["test_config"],
            setup["test_set"],
            organization_id=setup["org_id"],
        )
        test_run = setup["test_run"]
        test_run.attributes = {"metric_plan": plan}
        test_db.commit()
        test_db.refresh(test_run)

        matrix = get_verdict_matrix(test_db, test_run)

        test_order = plan["test_order"]
        index_a = test_order.index(str(setup["test_a"].id))
        index_b = test_order.index(str(setup["test_b"].id))

        rows_by_req = {str(row.requirement_id): row for row in matrix.rows}
        row_a = rows_by_req[str(setup["requirement_a"].id)]
        row_b = rows_by_req[str(setup["requirement_b"].id)]

        # Requirement A's row owns test A and disowns test B, and vice versa.
        assert row_a.verdicts[index_b] == "X"
        assert row_b.verdicts[index_a] == "X"

        # Test A passed, test B failed -- each must land on its own row only,
        # even though both metrics share the base key "Accuracy".
        assert row_a.verdicts[index_a] == "P"
        assert row_b.verdicts[index_b] == "F"
        assert (row_a.passed, row_a.failed) == (1, 0)
        assert (row_b.passed, row_b.failed) == (0, 1)

    def test_planned_verdicts_exclude_foreign_columns(
        self, test_db: Session, two_requirement_setup
    ):
        """Two requirements x one metric x one own test each = 2 planned
        cells, not 4 -- the other two are structurally not-applicable.
        """
        setup = two_requirement_setup
        plan = build_metric_plan(
            test_db,
            setup["test_config"],
            setup["test_set"],
            organization_id=setup["org_id"],
        )
        test_run = setup["test_run"]
        test_run.attributes = {"metric_plan": plan}
        test_db.commit()
        test_db.refresh(test_run)

        matrix = get_verdict_matrix(test_db, test_run)

        assert matrix.kpis.verdicts_planned == 2
        assert matrix.kpis.verdicts_resolved == 2


class TestSourceResolutionPerGroup:
    """Metric source is resolved per requirement group, not once from an
    arbitrary "sample" test. Asking a single test made the whole plan hostage
    to whichever test happened to sort first.
    """

    def test_requirement_less_first_test_does_not_blank_the_plan(
        self, test_db: Session, test_organization, db_user, db_endpoint, db_status
    ):
        org_id = test_organization.id
        user_id = db_user.id

        test_config = models.TestConfiguration(
            endpoint_id=db_endpoint.id, organization_id=org_id, user_id=user_id
        )
        test_db.add(test_config)
        test_db.flush()

        test_set = models.TestSet(
            name="Mixed Assignment Test Set",
            user_id=user_id,
            organization_id=org_id,
            status_id=db_status.id,
        )
        test_db.add(test_set)
        test_db.flush()
        test_config.test_set_id = test_set.id
        test_db.flush()

        requirement = models.Requirement(
            name="Req With Metrics", organization_id=org_id, user_id=user_id
        )
        test_db.add(requirement)
        test_db.flush()
        metric = _metric(test_db, org_id, user_id, name="Accuracy", scope=["Single-Turn"])
        _link_metric(test_db, requirement, metric, org_id, user_id)

        # Explicit ids: get_ordered_tests_for_test_set orders by Test.id, so
        # the all-zeroes id guarantees the requirement-less test is the one a
        # single-sample implementation would have asked.
        unassigned = models.Test(
            id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            user_id=user_id,
            organization_id=org_id,
            requirement_id=None,
        )
        assigned = models.Test(
            id=uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
            user_id=user_id,
            organization_id=org_id,
            requirement_id=requirement.id,
        )
        test_db.add_all([unassigned, assigned])
        test_db.flush()
        for test in (unassigned, assigned):
            _add_to_set(test_db, test, test_set, org_id, user_id)
        test_db.commit()

        plan = build_metric_plan(test_db, test_config, test_set, organization_id=str(org_id))

        assert plan["test_order"][0] == str(unassigned.id)

        by_id = {g["id"]: g for g in plan["requirements"]}
        assert [m["key"] for m in by_id[str(requirement.id)]["metrics"]] == ["Accuracy"]
        assert by_id[str(requirement.id)]["test_ids"] == [str(assigned.id)]

        # The unassigned group is still present as its own (empty) bucket.
        assert by_id[None]["metrics"] == []
        assert by_id[None]["test_ids"] == [str(unassigned.id)]


class TestScopeFilteredKeys:
    """cell_keys must carry the key the runtime will really write, not the
    plan's own row key. The runtime numbers duplicate names *after* scope
    filtering, so a survivor takes the bare name even when the plan gave that
    metric a suffix.
    """

    def test_survivor_of_scope_filter_maps_to_the_bare_key(
        self, test_db: Session, test_organization, db_user, db_endpoint, db_status
    ):
        org_id = test_organization.id
        user_id = db_user.id

        test_config = models.TestConfiguration(
            endpoint_id=db_endpoint.id, organization_id=org_id, user_id=user_id
        )
        test_db.add(test_config)
        test_db.flush()

        test_set = models.TestSet(
            name="Scope Filter Test Set",
            user_id=user_id,
            organization_id=org_id,
            status_id=db_status.id,
        )
        test_db.add(test_set)
        test_db.flush()
        test_config.test_set_id = test_set.id
        test_db.flush()

        requirement = models.Requirement(
            name="Req Mixed Scope", organization_id=org_id, user_id=user_id
        )
        test_db.add(requirement)
        test_db.flush()

        # Same name, different scopes. Sorted by (name, class_name, id) the
        # multi-turn one wins the bare key in the plan, so a single-turn test
        # must still resolve its own metric to "Accuracy" -- the runtime,
        # having filtered first, has only one metric left to name.
        multi = _metric(
            test_db,
            org_id,
            user_id,
            name="Accuracy",
            scope=["Multi-Turn"],
            class_name="AAAMetric",
        )
        single = _metric(
            test_db,
            org_id,
            user_id,
            name="Accuracy",
            scope=["Single-Turn"],
            class_name="ZZZMetric",
        )
        _link_metric(test_db, requirement, multi, org_id, user_id)
        _link_metric(test_db, requirement, single, org_id, user_id)

        single_turn_test = models.Test(
            user_id=user_id, organization_id=org_id, requirement_id=requirement.id
        )
        test_db.add(single_turn_test)
        test_db.flush()
        _add_to_set(test_db, single_turn_test, test_set, org_id, user_id)
        test_db.commit()

        plan = build_metric_plan(test_db, test_config, test_set, organization_id=str(org_id))

        keys = {m["id"]: m["key"] for m in plan["requirements"][0]["metrics"]}
        assert keys[str(multi.id)] == "Accuracy"
        assert keys[str(single.id)] == "Accuracy_1"

        # The single-turn test keeps only its own metric, and reads it under
        # the bare key the runtime will have used.
        per_test = plan["cell_keys"][str(single_turn_test.id)]
        assert per_test == {str(single.id): "Accuracy"}

        # And the multi-turn-only metric reads as not-applicable, not pending.
        test_run = models.TestRun(
            name="Scope Filter Run",
            user_id=user_id,
            organization_id=org_id,
            status_id=db_status.id,
            test_configuration_id=test_config.id,
            attributes={"metric_plan": plan},
        )
        test_db.add(test_run)
        test_db.commit()

        matrix = get_verdict_matrix(test_db, test_run)
        rows = {str(r.metric_id): r for r in matrix.rows}
        assert rows[str(multi.id)].verdicts == "X"
        assert rows[str(single.id)].verdicts == "."


class TestDuplicateResults:
    def test_newest_result_wins_per_cell(self, test_db: Session, verdict_matrix_setup):
        """A rescore (or a duplicate persist) leaves two test_result rows for
        one test. get_test_outcomes_for_run already takes the latest, so the
        verdict has to agree or the grid shows a stale cell beside a current
        status.
        """
        setup = verdict_matrix_setup
        plan = build_metric_plan(
            test_db,
            setup["test_config"],
            setup["test_set"],
            organization_id=setup["org_id"],
        )
        test_run = setup["test_run"]
        test_run.attributes = {"metric_plan": plan}

        # The fixture already recorded a passing result for test_a. Add a
        # newer failing one for the same (test, metric).
        fail_status = get_or_create_status(
            test_db,
            TestResultStatus.FAIL.value,
            "TestResult",
            organization_id=setup["org_id"],
        )
        newer = models.TestResult(
            test_run_id=test_run.id,
            test_configuration_id=setup["test_config"].id,
            test_id=setup["test_a"].id,
            organization_id=uuid.UUID(setup["org_id"]),
            user_id=setup["test_a"].user_id,
            status_id=fail_status.id,
            test_metrics={"metrics": {"Accuracy": {"is_successful": False}}},
            created_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        test_db.add(newer)
        test_db.commit()
        test_db.refresh(test_run)

        matrix = get_verdict_matrix(test_db, test_run)

        index_a = plan["test_order"].index(str(setup["test_a"].id))
        assert matrix.rows[0].verdicts[index_a] == "F"


class TestPassRateIsOverTests:
    def test_partially_passing_test_counts_as_one_failed_test(
        self, test_db: Session, test_organization, db_user, db_endpoint, db_status
    ):
        """One test, two metrics, one passing one failing. Over verdicts that
        is 50%; over tests it is 0%, because the test as a whole failed. The
        runs list and run header both report the latter, so the grid must too.
        """
        org_id = test_organization.id
        user_id = db_user.id

        test_config = models.TestConfiguration(
            endpoint_id=db_endpoint.id, organization_id=org_id, user_id=user_id
        )
        test_db.add(test_config)
        test_db.flush()

        test_set = models.TestSet(
            name="Pass Rate Test Set",
            user_id=user_id,
            organization_id=org_id,
            status_id=db_status.id,
        )
        test_db.add(test_set)
        test_db.flush()
        test_config.test_set_id = test_set.id
        test_db.flush()

        requirement = models.Requirement(name="Req Mixed", organization_id=org_id, user_id=user_id)
        test_db.add(requirement)
        test_db.flush()
        good = _metric(
            test_db, org_id, user_id, name="Good", scope=["Single-Turn"], class_name="GoodMetric"
        )
        bad = _metric(
            test_db, org_id, user_id, name="Bad", scope=["Single-Turn"], class_name="BadMetric"
        )
        _link_metric(test_db, requirement, good, org_id, user_id)
        _link_metric(test_db, requirement, bad, org_id, user_id)

        test = models.Test(user_id=user_id, organization_id=org_id, requirement_id=requirement.id)
        test_db.add(test)
        test_db.flush()
        _add_to_set(test_db, test, test_set, org_id, user_id)
        test_db.commit()

        plan = build_metric_plan(test_db, test_config, test_set, organization_id=str(org_id))

        fail_status = get_or_create_status(
            test_db, TestResultStatus.FAIL.value, "TestResult", organization_id=str(org_id)
        )
        test_run = models.TestRun(
            name="Pass Rate Run",
            user_id=user_id,
            organization_id=org_id,
            status_id=db_status.id,
            test_configuration_id=test_config.id,
            attributes={"metric_plan": plan},
        )
        test_db.add(test_run)
        test_db.flush()
        test_db.add(
            models.TestResult(
                test_run_id=test_run.id,
                test_configuration_id=test_config.id,
                test_id=test.id,
                organization_id=org_id,
                user_id=user_id,
                status_id=fail_status.id,
                test_metrics={
                    "metrics": {
                        "Good": {"is_successful": True},
                        "Bad": {"is_successful": False},
                    }
                },
            )
        )
        test_db.commit()
        test_db.refresh(test_run)

        matrix = get_verdict_matrix(test_db, test_run)

        rows = {r.metric_key: r for r in matrix.rows}
        assert rows["Good"].verdicts == "P"
        assert rows["Bad"].verdicts == "F"

        assert matrix.kpis.pass_rate == 0.0, "pass rate must be over tests, not verdicts"
        assert matrix.kpis.failures == 1
        assert matrix.kpis.verdicts_resolved == 2


class TestIsNewer:
    """The rule behind "newest result wins per cell". Covered directly
    because the integration test cannot control the order Postgres returns
    rows in, so it would pass by luck against a last-row-wins implementation.
    """

    def test_later_timestamp_wins(self):
        from rhesis.backend.app.services.test_run import _is_newer

        earlier = datetime(2026, 1, 1, tzinfo=timezone.utc)
        later = earlier + timedelta(hours=1)
        assert _is_newer(later, earlier) is True
        assert _is_newer(earlier, later) is False

    def test_equal_timestamps_take_the_later_row(self):
        from rhesis.backend.app.services.test_run import _is_newer

        same = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert _is_newer(same, same) is True

    def test_undated_never_displaces_a_dated_row(self):
        from rhesis.backend.app.services.test_run import _is_newer

        dated = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert _is_newer(None, dated) is False
        assert _is_newer(dated, None) is True
        assert _is_newer(None, None) is False
