"""
Regression coverage for _attach_tests_to_existing_test_set's soft-delete
handling.

The pre-created TestSet row is fetched with bypass_tenant_filter() (the row
was created by the router before this Celery task runs), using the standard
with_deleted() + _check_and_raise_if_deleted() pattern. A soft-deleted row
raises ItemDeletedException, same as everywhere else -- it's listed in
BaseTask.dont_autoretry_for, so Celery treats it as terminal instead of
retrying forever against a row that will never come back.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud import test_set as test_set_crud
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException


def _make_sdk_test_set():
    """Minimal SDK-like test set object with one test."""
    ts = MagicMock()
    ts.test_set_type = "single_turn"
    ts.tests = [
        {
            "prompt": {"content": "hello", "language_code": "en"},
            "requirement": "Harmful",
            "category": "Security",
            "topic": "Injection",
            "metadata": {"generated_by": "ConfigSynthesizer", "additional_info": {}},
        }
    ]
    return ts


@pytest.mark.unit
class TestAttachTestsToExistingTestSetSoftDelete:
    def test_raises_item_deleted_exception_for_deleted_test_set(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        from rhesis.backend.jobs.test_set import _attach_tests_to_existing_test_set

        test_set = models.TestSet(
            name="Pre-created Test Set",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add(test_set)
        test_db.commit()
        test_db.refresh(test_set)

        test_set_crud.delete_test_set(
            test_db, test_set.id, organization_id=test_org_id, user_id=authenticated_user_id
        )

        @contextmanager
        def fake_get_db_session():
            yield test_db

        mock_task = MagicMock()
        mock_task.get_db_session = fake_get_db_session

        with pytest.raises(ItemDeletedException):
            _attach_tests_to_existing_test_set(
                mock_task,
                _make_sdk_test_set(),
                test_set_id=str(test_set.id),
                org_id=test_org_id,
                user_id=authenticated_user_id,
            )
