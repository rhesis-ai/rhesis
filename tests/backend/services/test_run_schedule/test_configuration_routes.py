"""The plain test configuration routes leave a schedule alone, and delete clears it."""

from fastapi import status

from rhesis.backend.app import models
from rhesis.backend.app.schemas.test_run_schedule import ScheduleSpecIn
from rhesis.backend.app.services.test_run_schedule import service


def _scheduled(test_db, authenticated_user, schedule_test_set, schedule_endpoint):
    config = service.create_schedule(
        test_db,
        authenticated_user,
        test_set_id=schedule_test_set.id,
        endpoint_id=schedule_endpoint.id,
        spec=ScheduleSpecIn(name="Daily", cron="0 9 * * *"),
    )
    test_db.commit()
    return config


def test_put_keeps_the_schedule(
    authenticated_client, test_db, authenticated_user, schedule_test_set, schedule_endpoint
):
    config = _scheduled(test_db, authenticated_user, schedule_test_set, schedule_endpoint)
    stored = dict(config.attributes["schedule"])

    response = authenticated_client.put(
        f"/test_configurations/{config.id}", json={"attributes": {"execution_mode": "Sequential"}}
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    attributes = response.json()["attributes"]
    assert attributes["execution_mode"] == "Sequential"
    assert attributes["schedule"] == stored


def test_put_that_changes_the_schedule_is_refused(
    authenticated_client, test_db, authenticated_user, schedule_test_set, schedule_endpoint
):
    config = _scheduled(test_db, authenticated_user, schedule_test_set, schedule_endpoint)

    response = authenticated_client.put(
        f"/test_configurations/{config.id}",
        json={"attributes": {"schedule": {"cron": "* * * * *"}}},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "test_run_schedules" in response.json()["detail"]


def test_delete_clears_the_schedule(
    authenticated_client, test_db, authenticated_user, schedule_test_set, schedule_endpoint
):
    config = _scheduled(test_db, authenticated_user, schedule_test_set, schedule_endpoint)

    response = authenticated_client.delete(f"/test_configurations/{config.id}")

    assert response.status_code == status.HTTP_200_OK, response.text
    test_db.expire_all()
    row = test_db.get(models.TestConfiguration, config.id)
    assert "schedule" not in (row.attributes or {})
    assert row.status_id is None
