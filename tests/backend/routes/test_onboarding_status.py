"""GET /users/onboarding-status, end to end through auth and the tenant session."""

import uuid

import pytest
from fastapi import status
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.services.organization import EXAMPLE_PROJECT_NAME
from tests.backend.fixtures.rls import as_project
from tests.backend.fixtures.test_setup import create_test_organization_and_user

ONBOARDING_STATUS_URL = "/users/onboarding-status"


@pytest.fixture
def seeded_owner(test_db: Session, client):
    """A client signed in as the owner of a freshly seeded organization."""
    suffix = uuid.uuid4().hex[:8]
    org, user, token = create_test_organization_and_user(
        test_db,
        f"Onboarding Route Org {suffix}",
        f"onboarding_route_{suffix}@rhesis-test.com",
        "Onboarding Route Owner",
    )
    client.headers.update({"Authorization": f"Bearer {token.token}"})
    return client, str(org.id), str(user.id)


@pytest.mark.unit
class TestOnboardingStatusRoute:
    def test_new_org_reports_nothing_done(self, seeded_owner):
        client, _org_id, _user_id = seeded_owner

        response = client.get(ONBOARDING_STATUS_URL)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "project_created": False,
            "endpoint_setup": False,
            "users_invited": False,
            "test_cases_created": False,
        }

    def test_active_project_header_does_not_narrow_the_status(self, seeded_owner, test_db: Session):
        client, org_id, user_id = seeded_owner
        own = models.Project(name="Own Project", organization_id=org_id, user_id=user_id)
        test_db.add(own)
        test_db.flush()
        with as_project(test_db, own.id):
            test_db.add(
                models.Endpoint(
                    name="Own Endpoint",
                    connection_type="REST",
                    organization_id=org_id,
                    user_id=user_id,
                    project_id=own.id,
                )
            )
            test_db.flush()
        example = (
            test_db.query(models.Project)
            .filter(
                models.Project.organization_id == org_id,
                models.Project.name == EXAMPLE_PROJECT_NAME,
            )
            .one()
        )

        response = client.get(ONBOARDING_STATUS_URL, headers={"X-Project-Id": str(example.id)})

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["project_created"] is True
        assert body["endpoint_setup"] is True
