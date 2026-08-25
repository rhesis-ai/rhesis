"""
The execute endpoint must dispatch under the same Celery id it stores on the
test run.

Cancelling a queued test run works by revoking the id held in
``test_run.attributes["task_id"]``. If the route dispatches under a different
id, the revoke targets nothing and a queued run cannot be cancelled -- with no
error anywhere, because both halves succeed on their own.

That is exactly what a wrong keyword produces: ``launch_job`` takes
``celery_task_id``, and anything else lands in ``**kwargs`` and is forwarded to
the task as an argument, while ``launch_job`` quietly mints an id of its own.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


@pytest.mark.unit
class TestExecuteDispatchTaskId:
    def test_dispatches_under_the_id_stored_on_the_test_run(self):
        from rhesis.backend.app.routers.test_configuration import (
            execute_test_configuration_endpoint,
        )

        test_configuration_id = uuid4()
        organization_id, user_id = str(uuid4()), str(uuid4())

        current_user = MagicMock()
        current_user.id = user_id

        test_run = MagicMock()
        test_run.id = uuid4()

        captured = {}

        def fake_create_test_run(db, config, task_info=None, current_user_id=None):
            captured["stored_id"] = (task_info or {}).get("id")
            return test_run

        with (
            patch(
                "rhesis.backend.app.routers.test_configuration.test_configuration_crud.get_test_configuration",
                return_value=MagicMock(),
            ),
            patch(
                "rhesis.backend.app.routers.test_configuration.create_test_run",
                side_effect=fake_create_test_run,
            ),
            patch("rhesis.backend.app.routers.test_configuration.launch_job") as mock_launch,
        ):
            mock_launch.return_value = MagicMock(id="ignored")

            execute_test_configuration_endpoint(
                test_configuration_id=test_configuration_id,
                execution_request=None,
                db=MagicMock(),
                tenant_context=(organization_id, user_id),
                current_user=current_user,
            )

        # The keyword matters: `task_id=` would be swallowed by **kwargs and
        # forwarded to the task instead of setting Celery's dispatch id.
        assert "celery_task_id" in mock_launch.call_args.kwargs, (
            "launch_job must receive celery_task_id; a different keyword is "
            "forwarded to the task as an argument and the dispatch id is lost"
        )
        assert "task_id" not in mock_launch.call_args.kwargs

        assert mock_launch.call_args.kwargs["celery_task_id"] == captured["stored_id"], (
            "the id stored on the test run must be the id dispatched under, "
            "or revoking it cannot cancel the queued run"
        )
