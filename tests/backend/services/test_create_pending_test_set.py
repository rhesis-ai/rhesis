"""``create_pending_test_set`` stores the description the caller gave."""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.services import test_set as test_set_service


def _created_row_data(**kwargs) -> dict:
    with (
        patch.object(test_set_service, "get_or_create_status", return_value=MagicMock()),
        patch.object(test_set_service, "get_or_create_type_lookup", return_value=MagicMock()),
        patch.object(test_set_service.test_set_crud, "create_test_set") as create,
    ):
        test_set_service.create_pending_test_set(
            db=MagicMock(),
            name="R1 safety",
            organization_id="00000000-0000-0000-0000-000000000001",
            user_id="00000000-0000-0000-0000-000000000002",
            project_id="00000000-0000-0000-0000-000000000003",
            task_id="task-1",
            requested_tests=5,
            **kwargs,
        )
    return create.call_args.args[1]


@pytest.mark.unit
class TestCreatePendingTestSetDescription:
    def test_stores_the_given_description(self):
        assert _created_row_data(description="From the plan")["description"] == "From the plan"

    def test_without_one_the_description_is_left_empty(self):
        assert _created_row_data()["description"] is None
