"""Relationship sorts (``sort_by=endpoint.name`` etc.) order real rows through the API.

The sort LEFT JOINs the related tables. These check that the joins neither
duplicate nor drop rows (order, X-Total-Count and paging), and that they sit
alongside the list's own eager-load joins of the same tables.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from tests.backend.fixtures.rls import scope_to_project
from tests.backend.fixtures.test_setup import create_test_organization_and_user

# Insert order differs from both name orders, so a passing sort is not insert order.
ENDPOINT_AND_TEST_SET_NAMES = [("bravo", "yankee"), ("alpha", "zulu"), ("charlie", "xray")]


def _auth(token) -> dict:
    return {"Authorization": f"Bearer {token.token}"}


def _make_runs(db: Session, org, user) -> None:
    project = models.Project(name="Sort Project", organization_id=org.id, user_id=user.id)
    db.add(project)
    db.flush()
    scope_to_project(db, project.id)

    status = models.Status(name="Completed", organization_id=org.id, user_id=user.id)
    db.add(status)
    db.flush()

    for endpoint_name, test_set_name in ENDPOINT_AND_TEST_SET_NAMES:
        endpoint = models.Endpoint(
            name=endpoint_name,
            connection_type="REST",
            url="https://api.example.com/test",
            method="POST",
            organization_id=org.id,
            user_id=user.id,
            project_id=project.id,
        )
        test_set = models.TestSet(name=test_set_name, organization_id=org.id, user_id=user.id)
        db.add_all([endpoint, test_set])
        db.flush()
        config = models.TestConfiguration(
            endpoint_id=endpoint.id,
            test_set_id=test_set.id,
            organization_id=org.id,
            user_id=user.id,
        )
        db.add(config)
        db.flush()
        db.add(
            models.TestRun(
                name=f"run-{endpoint_name}",
                user_id=user.id,
                organization_id=org.id,
                status_id=status.id,
                test_configuration_id=config.id,
            )
        )
    db.commit()


def _run_names(response) -> list[str]:
    assert response.status_code == 200, response.text
    return [run["name"] for run in response.json()]


@pytest.mark.parametrize(
    ("sort_by", "ascending"),
    [
        ("endpoint.name", ["run-alpha", "run-bravo", "run-charlie"]),
        ("test_set.name", ["run-charlie", "run-bravo", "run-alpha"]),
    ],
)
def test_test_runs_sort_by_related_name(client: TestClient, test_db: Session, sort_by, ascending):
    org, user, token = create_test_organization_and_user(
        test_db, "Relationship Sort Org", "owner@relationship-sort.com", "Owner"
    )
    _make_runs(test_db, org, user)

    asc = client.get(
        "/test_runs/", params={"sort_by": sort_by, "sort_order": "asc"}, headers=_auth(token)
    )
    assert _run_names(asc) == ascending
    assert asc.headers["X-Total-Count"] == "3"

    desc = client.get(
        "/test_runs/", params={"sort_by": sort_by, "sort_order": "desc"}, headers=_auth(token)
    )
    assert _run_names(desc) == list(reversed(ascending))

    second_page = client.get(
        "/test_runs/",
        params={"sort_by": sort_by, "sort_order": "asc", "skip": 1, "limit": 1},
        headers=_auth(token),
    )
    assert _run_names(second_page) == [ascending[1]]


def test_tests_sort_by_topic_name(client: TestClient, test_db: Session):
    org, user, token = create_test_organization_and_user(
        test_db, "Topic Sort Org", "owner@topic-sort.com", "Owner"
    )
    topic_by_test = {"test-b": "beta", "test-a": "alpha", "test-none": None}
    for test_name, topic_name in topic_by_test.items():
        topic = None
        if topic_name:
            topic = models.Topic(name=topic_name, organization_id=org.id, user_id=user.id)
            test_db.add(topic)
            test_db.flush()
        test_db.add(
            models.Test(
                test_metadata={"label": test_name},
                topic_id=topic.id if topic else None,
                organization_id=org.id,
                user_id=user.id,
            )
        )
    test_db.commit()

    response = client.get(
        "/tests/", params={"sort_by": "topic.name", "sort_order": "asc"}, headers=_auth(token)
    )
    assert response.status_code == 200, response.text
    rows = response.json()
    # Postgres sorts NULLs last in ascending order; a test without a topic is kept.
    assert [(row.get("topic") or {}).get("name") for row in rows] == ["alpha", "beta", None]
    assert response.headers["X-Total-Count"] == "3"
