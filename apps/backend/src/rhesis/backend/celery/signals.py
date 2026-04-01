import logging

from celery.signals import task_failure, task_revoked

from rhesis.backend.tasks.enums import RunStatus

logger = logging.getLogger("celery.signals")

_EXECUTE_TEST_CONFIGURATION_TASK = "rhesis.backend.tasks.execute_test_configuration"


def _update_test_run_status(task_id: str, new_status: RunStatus, error_message: str = None):
    try:
        from rhesis.backend.app import crud
        from rhesis.backend.app.database import SessionLocal, set_session_variables
        from rhesis.backend.tasks.execution.run import update_test_run_status
        from rhesis.backend.tasks.utils import get_test_run_by_task_id

        with SessionLocal() as db:
            test_run = get_test_run_by_task_id(db, task_id)
            if test_run:
                org_id = str(test_run.organization_id) if test_run.organization_id else ""
                user_id = (
                    str(test_run.user_id)
                    if hasattr(test_run, "user_id") and test_run.user_id
                    else ""
                )
                set_session_variables(db, org_id, user_id)

                if new_status == RunStatus.FAILED:
                    from rhesis.backend.tasks.utils import update_test_run_with_error

                    update_test_run_with_error(
                        db, test_run, error_message or "Unknown error"
                    )
                else:
                    update_test_run_status(db, test_run, new_status.value)
                db.commit()
                logger.info(
                    f"Updated test_run {test_run.id} to {new_status.value} for task {task_id}"
                )
    except Exception as e:
        logger.error(f"Failed to update test run status for task {task_id}: {e}", exc_info=True)


@task_failure.connect
def handle_task_failure(
    sender=None, task_id=None, exception=None, args=None, kwargs=None,
    traceback=None, einfo=None, **kw
):
    task_name = getattr(sender, "name", str(sender))
    if task_name == _EXECUTE_TEST_CONFIGURATION_TASK:
        logger.info(
            f"Task failure caught for {task_name} (ID: {task_id}). Setting TestRun to Failed."
        )
        _update_test_run_status(
            task_id,
            RunStatus.FAILED,
            str(exception) if exception else "Task failed or worker crashed",
        )


@task_revoked.connect
def handle_task_revoked(sender=None, request=None, **kw):
    if request:
        task_id = request.id
        task_name = request.task
        if task_name == _EXECUTE_TEST_CONFIGURATION_TASK:
            logger.info(
                f"Task revoked caught for {task_name} (ID: {task_id}). Setting TestRun to Cancelled."
            )
            _update_test_run_status(task_id, RunStatus.CANCELLED)
