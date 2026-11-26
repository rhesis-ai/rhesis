"""Start a group of test runs: one per test set and experiment version, sharing a batch id.

The quota and job slots are checked for the whole group, and every run is created (its
models checked, its experiment resolved) before any is queued, so a refusal starts nothing.
"""

import logging
import uuid
from itertools import product
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud import test_set as test_set_crud
from rhesis.backend.app.crud.test_configuration import get_test_configuration
from rhesis.backend.app.schemas.test_run_batch import (
    MAX_BATCH_RUNS,
    BatchExperiment,
    TestRunBatchCreate,
)
from rhesis.backend.app.services.job_capacity import enforce_job_capacity
from rhesis.backend.app.services.test_configuration_execution import (
    SUBMIT_FAILED_MESSAGE,
    dispatch_run,
    prepare_run,
)
from rhesis.backend.app.services.test_set import (
    count_test_set_tests,
    create_test_set_configuration,
    enforce_test_execution_quota,
    resolve_execution_targets,
)

logger = logging.getLogger(__name__)


def _resolve_test_sets(
    db: Session, user: models.User, request: TestRunBatchCreate
) -> List[models.TestSet]:
    """The group's test sets, each checked the way a single run checks it."""
    if request.test_set_tag is not None:
        candidates = [
            str(test_set.id)
            for test_set in test_set_crud.get_test_sets_tagged(db, request.test_set_tag)
        ]
        if not candidates:
            raise ValueError(f"No test sets carry the tag: {request.test_set_tag}.")
    else:
        candidates = list(dict.fromkeys(str(test_set_id) for test_set_id in request.test_set_ids))

    test_sets, problems = [], []
    for identifier in candidates:
        try:
            test_set, _ = resolve_execution_targets(
                db, identifier, request.endpoint_id, user, request.run_settings.tests_tagged
            )
            test_sets.append(test_set)
        except ValueError as exc:
            problems.append(str(exc))
    if problems:
        raise ValueError(" ".join(problems))
    return test_sets


def _batch_attributes(
    batch_id: str, size: int, index: int, request: TestRunBatchCreate
) -> Dict[str, Any]:
    attributes: Dict[str, Any] = {
        "batch_id": batch_id,
        "batch_size": size,
        "batch_index": index,
    }
    if request.experiments:
        attributes["batch_experiments"] = [
            {"experiment_id": str(e.experiment_id), "version": e.version}
            for e in request.experiments
        ]
    if request.test_set_tag is not None:
        attributes["batch_set_tag"] = request.test_set_tag
    return attributes


def start_batch(db: Session, user: models.User, request: TestRunBatchCreate) -> Dict[str, Any]:
    """Start every run of the group, or none: every run is prepared before any is queued."""
    settings = request.run_settings
    test_sets = _resolve_test_sets(db, user, request)
    experiments: List[Optional[BatchExperiment]] = list(request.experiments) or [None]
    size = len(test_sets) * len(experiments)
    if size > MAX_BATCH_RUNS:
        raise ValueError(
            f"This group would start {size} runs; a group can start at most {MAX_BATCH_RUNS}."
        )

    organization_id, user_id = str(user.organization_id), str(user.id)
    tests_per_round = sum(
        count_test_set_tests(db, test_set.id, settings.tests_tagged) for test_set in test_sets
    )
    enforce_test_execution_quota(db, organization_id, user_id, tests_per_round * len(experiments))
    enforce_job_capacity(db, organization_id, user_id, slots=size)

    is_group = size > 1 or request.test_set_tag is not None
    batch_id = str(uuid.uuid4()) if is_group else None
    metrics = [
        {"id": str(m.id), "name": m.name, "scope": m.scope} for m in settings.metrics or []
    ] or None

    prepared = []
    # One SAVEPOINT for the whole group: a member refused for its models or its experiment
    # takes every configuration and run back with it.
    savepoint = db.begin_nested()
    try:
        for index, (test_set, experiment) in enumerate(product(test_sets, experiments)):
            attributes = dict(settings.execution_options or {})
            if batch_id:
                attributes |= _batch_attributes(batch_id, size, index, request)
            _, _, config_id = create_test_set_configuration(
                db,
                str(test_set.id),
                request.endpoint_id,
                user,
                test_configuration_attributes=attributes,
                organization_id=organization_id,
                user_id=user_id,
                metrics=metrics,
                reference_test_run_id=settings.reference_test_run_id,
                execution_model_id=settings.execution_model_id,
                evaluation_model_id=settings.evaluation_model_id,
                experiment_id=experiment.experiment_id if experiment else None,
                experiment_version=experiment.version if experiment else None,
                tests_tagged=settings.tests_tagged,
                check_quota=False,
            )
            config = get_test_configuration(
                db, uuid.UUID(config_id), organization_id=organization_id, user_id=user_id
            )
            test_run, celery_task_id = prepare_run(db, config, user)
            prepared.append((test_set, experiment, config, test_run, celery_task_id))
    except Exception:
        if savepoint.is_active:
            savepoint.rollback()
        raise
    db.commit()

    _dispatch_all(db, user, prepared)
    logger.info("Started group of %d runs (batch %s)", size, batch_id)
    return {
        "batch_id": batch_id,
        "test_set_tag": request.test_set_tag,
        "members": [
            {
                "test_set_id": test_set.id,
                "test_set_name": test_set.name,
                "experiment_id": experiment.experiment_id if experiment else None,
                "version": experiment.version if experiment else None,
                "test_configuration_id": config.id,
                "test_run_id": test_run.id,
                "test_run_name": test_run.name,
            }
            for test_set, experiment, config, test_run, _ in prepared
        ],
    }


def _dispatch_all(db: Session, user: models.User, prepared: list) -> None:
    """Queue every prepared run. If the broker refuses one, the runs not queued yet fail too,
    so none is left Queued without a job behind it."""
    from rhesis.backend.jobs.enums import RunStatus
    from rhesis.backend.jobs.execution.run import update_test_run_status

    for position, (_, _, config, test_run, celery_task_id) in enumerate(prepared):
        try:
            dispatch_run(db, config, test_run, user, celery_task_id)
        except Exception:
            for _, _, _, waiting, _ in prepared[position + 1 :]:
                update_test_run_status(
                    db, waiting, RunStatus.FAILED.value, error=SUBMIT_FAILED_MESSAGE
                )
            db.commit()
            raise
