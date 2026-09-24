"""get_stored_outputs_for_run: the outputs a batch re-score replays."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud.test_result import get_stored_outputs_for_run


def test_newest_output_per_test_wins(
    test_db: Session, test_organization, db_user, db_endpoint, db_status
):
    org_id, user_id = test_organization.id, db_user.id
    config = models.TestConfiguration(
        endpoint_id=db_endpoint.id, organization_id=org_id, user_id=user_id
    )
    test_db.add(config)
    test_db.flush()
    run = models.TestRun(
        name="Reference Run",
        user_id=user_id,
        organization_id=org_id,
        status_id=db_status.id,
        test_configuration_id=config.id,
    )
    test = models.Test(user_id=user_id, organization_id=org_id)
    test_db.add_all([run, test])
    test_db.flush()

    now = datetime.now(timezone.utc)
    for output, created_at in (
        ({"output": "old"}, now - timedelta(minutes=1)),
        ({"output": "new"}, now),
    ):
        test_db.add(
            models.TestResult(
                test_run_id=run.id,
                test_configuration_id=config.id,
                test_id=test.id,
                organization_id=org_id,
                user_id=user_id,
                test_output=output,
                created_at=created_at,
            )
        )
    test_db.commit()

    outputs = get_stored_outputs_for_run(test_db, run.id, str(org_id))

    assert outputs == {str(test.id): {"output": "new"}}
