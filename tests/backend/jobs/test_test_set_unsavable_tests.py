"""A generated test that does not fit the test schema is dropped, not the whole set."""

import uuid
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models

MULTI_TURN = {
    "test_configuration": {"goal": "Get a refund", "min_turns": 2, "max_turns": 5},
    "requirement": "Refunds",
    "category": "Support",
    "topic": "Orders",
    "test_type": "Multi-Turn",
}


def _test_set(tests):
    ts = MagicMock()
    ts.name = "Generated Set"
    ts.description = "Auto-generated"
    ts.short_description = "Short"
    ts.test_set_type = "multi_turn"
    ts.metadata = {}
    ts.tests = tests
    return ts


@pytest.mark.unit
class TestUnsavableGeneratedTests:
    @patch("rhesis.backend.jobs.test_set.bulk_create_test_set")
    def test_a_test_that_does_not_fit_is_dropped_and_the_rest_saved(self, bulk_create):
        from rhesis.backend.jobs.test_set import _save_test_set_to_database

        bad = {**MULTI_TURN, "test_configuration": {"goal": "   "}}
        ts = _test_set([dict(MULTI_TURN), bad])

        _save_test_set_to_database(MagicMock(), ts, org_id="org", user_id="user")

        saved = bulk_create.call_args.kwargs["test_set_data"]["tests"]
        assert len(saved) == 1
        assert ts.tests == [MULTI_TURN]

    @patch("rhesis.backend.jobs.test_set.bulk_create_test_set")
    def test_when_no_test_fits_it_fails_without_blaming_the_model(self, bulk_create):
        from rhesis.backend.jobs.test_set import (
            GeneratedTestsUnsavable,
            _save_test_set_to_database,
        )

        bad = {**MULTI_TURN, "test_configuration": {"goal": "x", "min_turns": 9, "max_turns": 2}}

        with pytest.raises(GeneratedTestsUnsavable, match="None of the 1 generated tests"):
            _save_test_set_to_database(MagicMock(), _test_set([bad]), org_id="o", user_id="u")
        bulk_create.assert_not_called()


@pytest.mark.unit
class TestUnsavableTestsOnTheAttachPath:
    """The UI pre-creates the test set, so its generations save through this path."""

    def test_when_no_test_fits_it_fails_before_touching_the_set(self):
        from rhesis.backend.jobs.test_set import (
            GeneratedTestsUnsavable,
            _attach_tests_to_existing_test_set,
        )

        bad = {**MULTI_TURN, "test_configuration": {"goal": "   "}}
        task = MagicMock()

        with pytest.raises(GeneratedTestsUnsavable):
            _attach_tests_to_existing_test_set(
                task, _test_set([bad]), test_set_id=str(uuid.uuid4()), org_id="o", user_id="u"
            )
        task.get_db_session.assert_not_called()

    def test_only_the_tests_that_fit_are_attached(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        from rhesis.backend.jobs.test_set import _attach_tests_to_existing_test_set

        test_set = models.TestSet(
            name="Pre-created", organization_id=test_org_id, user_id=authenticated_user_id
        )
        test_db.add(test_set)
        test_db.commit()

        @contextmanager
        def session():
            yield test_db

        task = MagicMock()
        task.get_db_session = session
        bad = {**MULTI_TURN, "test_configuration": {"goal": "x", "min_turns": 9, "max_turns": 2}}

        _attach_tests_to_existing_test_set(
            task,
            _test_set([dict(MULTI_TURN), bad]),
            test_set_id=str(test_set.id),
            org_id=test_org_id,
            user_id=authenticated_user_id,
        )

        test_db.refresh(test_set)
        assert len(test_set.tests) == 1
