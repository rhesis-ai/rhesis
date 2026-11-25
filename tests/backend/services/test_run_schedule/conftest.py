"""A project with an endpoint and test sets that hold a test, for schedule service tests."""

import uuid

import pytest

from rhesis.backend.app import models
from rhesis.backend.app.constants import TestType
from rhesis.backend.app.utils.crud_utils import get_or_create_status, get_or_create_type_lookup
from tests.backend.fixtures.rls import scope_to_project


@pytest.fixture
def schedule_project(test_db, test_org_id, authenticated_user_id):
    project = models.Project(
        name=f"Schedules {uuid.uuid4().hex[:8]}",
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    test_db.add(project)
    test_db.flush()
    scope_to_project(test_db, project.id)
    return project


@pytest.fixture
def schedule_endpoint(test_db, test_org_id, authenticated_user_id, schedule_project):
    endpoint = models.Endpoint(
        name=f"Endpoint {uuid.uuid4().hex[:8]}",
        organization_id=test_org_id,
        user_id=authenticated_user_id,
        project_id=schedule_project.id,
        connection_type="rest",
        url="https://example.com/api",
    )
    test_db.add(endpoint)
    test_db.flush()
    return endpoint


@pytest.fixture
def make_test_set(test_db, test_org_id, authenticated_user_id):
    """Build a test set holding one test."""

    def _make(name: str = "Weekday regression set") -> models.TestSet:
        active = get_or_create_status(
            test_db, "Active", "General", organization_id=test_org_id, commit=False
        )
        test_type = get_or_create_type_lookup(
            test_db, "TestType", TestType.SINGLE_TURN.value, test_org_id, authenticated_user_id
        )
        test_set = models.TestSet(
            name=name,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            status_id=active.id,
        )
        test = models.Test(
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            status_id=active.id,
            test_type_id=test_type.id,
        )
        test_db.add_all([test_set, test])
        test_db.flush()
        test_db.execute(
            models.test_test_set_association.insert().values(
                test_id=test.id,
                test_set_id=test_set.id,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )
        )
        test_db.flush()
        return test_set

    return _make


@pytest.fixture
def schedule_test_set(make_test_set):
    return make_test_set()
