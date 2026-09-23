"""The requirement-metric coverage preflight check, against a real Postgres.

A requirement counts as covered only when it has a metric whose scope fits
its tests: a multi-turn test under a requirement with only single-turn
metrics goes unscored exactly like one under a requirement with none.
"""

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.constants import TestType
from rhesis.backend.app.schemas.preflight import PreflightCheckStatus
from rhesis.backend.app.services.preflight.checks import _requirement_metric_coverage
from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup


@pytest.fixture
def coverage(test_db: Session, test_organization, db_user, db_status):
    org_id = test_organization.id
    user_id = db_user.id
    test_set = models.TestSet(
        name="Coverage Test Set", user_id=user_id, organization_id=org_id, status_id=db_status.id
    )
    test_db.add(test_set)
    test_db.flush()

    def lookup(type_name, value):
        return get_or_create_type_lookup(test_db, type_name, value, str(org_id), str(user_id))

    def requirement(name, *, metric_scopes=(), multi_turn=False):
        req = models.Requirement(name=name, organization_id=org_id, user_id=user_id)
        test_db.add(req)
        test_db.flush()
        for scope in metric_scopes:
            metric = models.Metric(
                metric_scope=scope,
                name=f"{name} metric",
                class_name="AccuracyMetric",
                score_type="numeric",
                evaluation_prompt="Evaluate",
                backend_type_id=lookup("BackendType", "rhesis").id,
                metric_type_id=lookup("MetricType", "custom-prompt").id,
                organization_id=org_id,
                user_id=user_id,
            )
            test_db.add(metric)
            test_db.flush()
            test_db.execute(
                models.requirement_metric_association.insert().values(
                    requirement_id=req.id,
                    metric_id=metric.id,
                    organization_id=org_id,
                    user_id=user_id,
                )
            )
        test_type = TestType.MULTI_TURN if multi_turn else TestType.SINGLE_TURN
        test = models.Test(
            user_id=user_id,
            organization_id=org_id,
            requirement_id=req.id,
            test_type_id=lookup("TestType", test_type.value).id,
        )
        test_db.add(test)
        test_db.flush()
        test_db.execute(
            models.test_test_set_association.insert().values(
                test_id=test.id, test_set_id=test_set.id, organization_id=org_id, user_id=user_id
            )
        )
        test_db.commit()

    def check():
        return _requirement_metric_coverage(test_db, test_set.id, str(org_id))

    return requirement, check


@pytest.mark.integration
class TestRequirementMetricCoverage:
    def test_all_covered(self, coverage):
        requirement, check = coverage
        requirement("Single", metric_scopes=[["Single-Turn"]])
        requirement("Multi", metric_scopes=[["Multi-Turn"]], multi_turn=True)

        assert check().status == PreflightCheckStatus.PASSED

    def test_requirement_without_metrics_is_flagged_as_unscored(self, coverage):
        requirement, check = coverage
        requirement("Covered", metric_scopes=[["Single-Turn"]])
        requirement("Bare")

        result = check()
        assert result.status == PreflightCheckStatus.WARNING
        assert "1 of 2" in result.message
        assert "Bare" in result.detail
        assert "Covered" not in result.detail
        # The run doesn't skip these tests, it runs them unscored.
        assert "won't get a pass/fail verdict" in result.detail

    def test_metrics_of_the_wrong_scope_do_not_cover(self, coverage):
        requirement, check = coverage
        requirement(
            "Multi with single-turn metric", metric_scopes=[["Single-Turn"]], multi_turn=True
        )

        result = check()
        assert result.status == PreflightCheckStatus.WARNING
        assert "Multi with single-turn metric" in result.detail

    def test_one_fitting_metric_is_enough(self, coverage):
        requirement, check = coverage
        requirement(
            "Mixed", metric_scopes=[["Single-Turn"], ["Multi-Turn", "Single-Turn"]], multi_turn=True
        )

        assert check().status == PreflightCheckStatus.PASSED
