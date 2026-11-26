"""Start a run of an existing test configuration.

One path for every way a run starts from a configuration: the execute route, the test set
execute route, and scheduled runs.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Literal

from sqlalchemy.orm import Session

from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.job_capacity import JobCapacityExceededError

logger = logging.getLogger(__name__)

RunTrigger = Literal["manual", "schedule"]

SUBMIT_FAILED_MESSAGE = "Failed to submit the test run for execution."


class RunSubmissionError(Exception):
    """The run was created but could not be handed to a worker; it is marked Failed."""


def build_parameters_ref(
    experiment_id: Any = None, version: str | None = None, environment: str | None = None
) -> dict[str, str]:
    """The experiment, version and environment a run resolves its parameters from."""
    parameters_ref = {}
    if experiment_id is not None:
        parameters_ref["experiment_id"] = str(experiment_id)
    if version and str(version).strip():
        parameters_ref["version"] = str(version).strip()
    if environment is not None:
        parameters_ref["environment"] = str(environment)
    return parameters_ref


def execute_configuration(
    db: Session,
    config: TestConfiguration,
    user: User,
    *,
    trigger: RunTrigger | None = None,
    scheduled_for: datetime | None = None,
    parameters_ref: dict[str, str] | None = None,
    check_quota: bool = True,
) -> tuple[Any, TestRun]:
    """Create a Queued run of ``config`` as ``user`` and dispatch it.

    Returns the Celery result and the run. ``trigger`` is stored on the run only when given,
    so runs from the existing paths look exactly as before. Raises ``QuotaExceededError``,
    the model check's errors, ``JobCapacityExceededError`` or ``RunSubmissionError``.
    """
    from rhesis.backend.app.services.test_set import enforce_test_run_quota, tagged_test_filter

    if check_quota and config.test_set_id:
        enforce_test_run_quota(
            db,
            str(config.organization_id),
            str(user.id),
            config.test_set_id,
            tagged_test_filter(config.attributes),
        )

    if parameters_ref:
        attributes = dict(config.attributes or {})
        attributes["parameters_ref"] = parameters_ref
        config.attributes = attributes
        db.commit()

    test_run, celery_task_id = prepare_run(
        db, config, user, trigger=trigger, scheduled_for=scheduled_for
    )
    db.commit()

    result = dispatch_run(db, config, test_run, user, celery_task_id)
    return result, test_run


def prepare_run(
    db: Session,
    config: TestConfiguration,
    user: User,
    *,
    trigger: RunTrigger | None = None,
    scheduled_for: datetime | None = None,
) -> tuple[TestRun, str]:
    """Check the run's models and create it Queued, without committing or dispatching.

    Returns the run and the Celery task id to dispatch it under. Raises the model check's
    errors, and the experiment resolution's when its parameters can't be resolved.
    """
    from rhesis.backend.jobs.execution.run import create_test_run, plan_run_for_user

    # Metrics are resolved here, so this is where the run's models can be checked.
    metric_plan = plan_run_for_user(db, config, user)

    # Stored on the run before dispatch, so cancel can always revoke it.
    celery_task_id = str(uuid.uuid4())
    test_run = create_test_run(
        db,
        config,
        task_info={"id": celery_task_id},
        current_user_id=str(user.id),
        metric_plan=metric_plan,
    )
    if trigger is not None:
        _stamp_trigger(test_run, trigger, scheduled_for)
    return test_run, celery_task_id


def _stamp_trigger(test_run: TestRun, trigger: RunTrigger, scheduled_for: datetime | None) -> None:
    attributes = dict(test_run.attributes or {})
    attributes["trigger"] = trigger
    if scheduled_for is not None:
        attributes["scheduled_for"] = scheduled_for.isoformat()
    test_run.attributes = attributes


def dispatch_run(
    db: Session, config: TestConfiguration, test_run: TestRun, user: User, celery_task_id: str
):
    """Queue a committed run's job; on failure, mark the run Failed and raise."""
    from rhesis.backend.jobs import launch_job
    from rhesis.backend.jobs.enums import RunStatus
    from rhesis.backend.jobs.execution.run import update_test_run_status
    from rhesis.backend.jobs.test_configuration import execute_test_configuration

    try:
        return launch_job(
            execute_test_configuration,
            str(config.id),
            test_run_id=str(test_run.id),
            current_user=user,
            celery_task_id=celery_task_id,
            db=db,
            entity_type="TestRun",
            entity_id=str(test_run.id),
        )
    except Exception as exc:
        # The stored text is shown in the UI, and a broker error carries the connection
        # string with it, so the full text goes to the log only.
        logger.exception("Failed to submit test configuration %s for execution", config.id)
        update_test_run_status(db, test_run, RunStatus.FAILED.value, error=SUBMIT_FAILED_MESSAGE)
        db.commit()
        if isinstance(exc, JobCapacityExceededError):  # re-checked at dispatch
            raise
        raise RunSubmissionError(SUBMIT_FAILED_MESSAGE) from exc
