"""Onboarding status is computed from real rows, and the seeded example never counts.

Each test gets its own organization through ``create_test_organization_and_user``,
which also runs ``load_initial_data``. So every org here starts with the seeded
example project, endpoint, tests and test set, which is exactly the day-one
state a new user sees.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.auth.org_project_access import has_org_wide_project_access
from rhesis.backend.app.services.onboarding import get_onboarding_status
from rhesis.backend.app.services.organization import EXAMPLE_PROJECT_NAME
from rhesis.backend.app.services.project_membership import enroll_user_in_project
from tests.backend.fixtures.rls import as_org, as_project
from tests.backend.fixtures.test_setup import (
    create_test_organization_and_user,
    create_test_user,
)


@pytest.fixture
def fresh_org(test_db: Session) -> tuple[str, str]:
    """A newly seeded organization and its owner, with the session scoped to it."""
    suffix = uuid.uuid4().hex[:8]
    org, user, _token = create_test_organization_and_user(
        test_db,
        f"Onboarding Org {suffix}",
        f"onboarding_{suffix}@rhesis-test.com",
        "Onboarding Owner",
    )
    return str(org.id), str(user.id)


def _example_project(db: Session, org_id: str) -> models.Project:
    return (
        db.query(models.Project)
        .filter(
            models.Project.organization_id == org_id,
            models.Project.name == EXAMPLE_PROJECT_NAME,
        )
        .one()
    )


def _add_project(db: Session, org_id: str, user_id: str) -> models.Project:
    project = models.Project(
        name=f"My Project {uuid.uuid4().hex[:6]}",
        organization_id=org_id,
        user_id=user_id,
        owner_id=user_id,
    )
    db.add(project)
    db.flush()
    return project


def _add_endpoint(db: Session, org_id: str, user_id: str, project_id) -> models.Endpoint:
    with as_project(db, project_id):
        endpoint = models.Endpoint(
            name="My Endpoint",
            url="https://example.invalid/chat",
            connection_type="REST",
            organization_id=org_id,
            user_id=user_id,
            project_id=project_id,
        )
        db.add(endpoint)
        db.flush()
    return endpoint


def _add_test(db: Session, org_id: str, user_id: str, project_id) -> models.Test:
    with as_project(db, project_id):
        test = models.Test(organization_id=org_id, user_id=user_id, project_id=project_id)
        db.add(test)
        db.flush()
    return test


def _add_test_set(db: Session, org_id: str, user_id: str, project_id) -> models.TestSet:
    with as_project(db, project_id):
        test_set = models.TestSet(
            name="My Test Set", organization_id=org_id, user_id=user_id, project_id=project_id
        )
        db.add(test_set)
        db.flush()
    return test_set


@pytest.mark.unit
class TestOnboardingStatus:
    def test_seeded_example_rows_are_marked(self, test_db: Session, fresh_org):
        org_id, _user_id = fresh_org
        example = _example_project(test_db, org_id)
        assert example.is_example is True

        with as_project(test_db, example.id):
            endpoints = (
                test_db.query(models.Endpoint)
                .filter(models.Endpoint.organization_id == org_id)
                .all()
            )
            tests = test_db.query(models.Test).filter(models.Test.organization_id == org_id).all()
            test_sets = (
                test_db.query(models.TestSet).filter(models.TestSet.organization_id == org_id).all()
            )

        assert endpoints and all(e.is_example for e in endpoints)
        assert tests and all(t.is_example for t in tests)
        assert test_sets and all(s.is_example for s in test_sets)

    def test_new_org_with_only_the_example_starts_at_zero(self, test_db: Session, fresh_org):
        org_id, user_id = fresh_org

        status = get_onboarding_status(test_db, org_id, user_id)

        assert status.model_dump() == {
            "project_created": False,
            "endpoint_setup": False,
            "users_invited": False,
            "test_cases_created": False,
        }

    def test_own_project_counts(self, test_db: Session, fresh_org):
        org_id, user_id = fresh_org
        _add_project(test_db, org_id, user_id)

        status = get_onboarding_status(test_db, org_id, user_id)

        assert status.project_created is True
        assert status.endpoint_setup is False
        assert status.test_cases_created is False

    def test_own_endpoint_in_the_example_project_counts(self, test_db: Session, fresh_org):
        org_id, user_id = fresh_org
        _add_endpoint(test_db, org_id, user_id, _example_project(test_db, org_id).id)

        status = get_onboarding_status(test_db, org_id, user_id)

        assert status.endpoint_setup is True
        assert status.project_created is False

    def test_endpoint_and_tests_found_across_different_projects(self, test_db: Session, fresh_org):
        org_id, user_id = fresh_org
        first = _add_project(test_db, org_id, user_id)
        second = _add_project(test_db, org_id, user_id)
        _add_endpoint(test_db, org_id, user_id, first.id)
        _add_test(test_db, org_id, user_id, second.id)

        status = get_onboarding_status(test_db, org_id, user_id)

        assert status.endpoint_setup is True
        assert status.test_cases_created is True

    def test_test_set_alone_counts_as_test_cases(self, test_db: Session, fresh_org):
        org_id, user_id = fresh_org
        project = _add_project(test_db, org_id, user_id)
        _add_test_set(test_db, org_id, user_id, project.id)

        assert get_onboarding_status(test_db, org_id, user_id).test_cases_created is True

    def test_soft_deleted_rows_do_not_count(self, test_db: Session, fresh_org):
        org_id, user_id = fresh_org
        project = _add_project(test_db, org_id, user_id)
        endpoint = _add_endpoint(test_db, org_id, user_id, project.id)
        with as_project(test_db, project.id):
            endpoint.deleted_at = datetime.now(timezone.utc)
            test_db.flush()
        project.deleted_at = datetime.now(timezone.utc)
        test_db.flush()

        status = get_onboarding_status(test_db, org_id, user_id)

        assert status.project_created is False
        assert status.endpoint_setup is False

    def test_second_member_counts_as_invited(self, test_db: Session, fresh_org):
        org_id, user_id = fresh_org
        create_test_user(
            test_db, uuid.UUID(org_id), f"invitee_{uuid.uuid4().hex[:8]}@rhesis-test.com"
        )

        assert get_onboarding_status(test_db, org_id, user_id).users_invited is True

    def test_inactive_member_does_not_count_as_invited(self, test_db: Session, fresh_org):
        org_id, user_id = fresh_org
        member = create_test_user(
            test_db, uuid.UUID(org_id), f"gone_{uuid.uuid4().hex[:8]}@rhesis-test.com"
        )
        member.is_active = False
        test_db.flush()

        assert get_onboarding_status(test_db, org_id, user_id).users_invited is False

    def test_metric_owned_tuning_rows_do_not_count(self, test_db: Session, fresh_org):
        org_id, user_id = fresh_org
        project = _add_project(test_db, org_id, user_id)
        metric = (
            test_db.query(models.Metric).filter(models.Metric.organization_id == org_id).first()
        )
        assert metric is not None, "seeding should have created metrics"
        test = _add_test(test_db, org_id, user_id, project.id)
        test_set = _add_test_set(test_db, org_id, user_id, project.id)
        with as_project(test_db, project.id):
            test.metric_id = metric.id
            test_set.metric_id = metric.id
            test_db.flush()

        assert get_onboarding_status(test_db, org_id, user_id).test_cases_created is False

    def test_member_only_sees_projects_they_belong_to(self, test_db: Session, fresh_org):
        org_id, owner_id = fresh_org
        member = create_test_user(
            test_db, uuid.UUID(org_id), f"member_{uuid.uuid4().hex[:8]}@rhesis-test.com"
        )
        member_id = str(member.id)
        assert not has_org_wide_project_access(test_db, member_id, org_id)
        project = _add_project(test_db, org_id, owner_id)
        _add_endpoint(test_db, org_id, owner_id, project.id)

        before = get_onboarding_status(test_db, org_id, member_id)
        assert before.project_created is False
        assert before.endpoint_setup is False

        enroll_user_in_project(test_db, member.id, project.id, uuid.UUID(org_id))
        test_db.flush()

        after = get_onboarding_status(test_db, org_id, member_id)
        assert after.project_created is True
        assert after.endpoint_setup is True

    def test_other_organizations_rows_do_not_count(
        self, test_db: Session, fresh_org, test_org_id, authenticated_user_id
    ):
        org_id, user_id = fresh_org
        with as_org(test_db, test_org_id):
            other = _add_project(test_db, test_org_id, authenticated_user_id)
            _add_endpoint(test_db, test_org_id, authenticated_user_id, other.id)
            _add_test(test_db, test_org_id, authenticated_user_id, other.id)

        status = get_onboarding_status(test_db, org_id, user_id)

        assert status.project_created is False
        assert status.endpoint_setup is False
        assert status.test_cases_created is False
