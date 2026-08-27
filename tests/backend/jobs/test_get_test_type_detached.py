"""Regression tests for `get_test_type` on detached Test instances.

The batch execution path expunges its Test objects (`batch/context.py`) and only
re-checks the test type afterwards (`batch/runner.py`). If the type silently
degrades to Single-Turn once detached, a Multi-Turn test runs through the
single-turn path.
"""

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from rhesis.backend.app.constants import TestType
from rhesis.backend.jobs.execution.modes import get_test_type


@pytest.fixture
def multi_turn_test(
    test_db: Session,
    test_org_id: str,
    authenticated_user_id: str,
    db_status,
):
    """A Test row correctly typed Multi-Turn, with a goal, as the app would store it."""
    from rhesis.backend.app.models import Test, TypeLookup

    multi_turn_type = TypeLookup(
        type_name="TestType",
        type_value=TestType.MULTI_TURN,
        description="Agentic multi-turn conversation test",
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    test_db.add(multi_turn_type)
    test_db.flush()

    test = Test(
        test_type_id=multi_turn_type.id,
        test_configuration={"goal": "Convince the agent to reveal its system prompt"},
        status_id=db_status.id,
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    test_db.add(test)
    test_db.commit()

    # Re-fetch through the same call the batch prefetch uses, so the instance
    # starts in the same load state production sees (test_type NOT eager-loaded).
    test_db.expire_all()
    from rhesis.backend.app.crud import test as test_crud

    return test_crud.get_test(test_db, test.id, organization_id=test_org_id)


@pytest.mark.unit
class TestGetTestTypeDetached:
    def test_test_type_relationship_is_not_eager_loaded(self, multi_turn_test):
        """Establishes the precondition: test_crud.get_test leaves test_type unloaded."""
        assert "test_type" in sa_inspect(multi_turn_test).unloaded

    def test_attached_instance_resolves_multi_turn(self, multi_turn_test):
        """While a session is attached, resolution is correct."""
        assert get_test_type(multi_turn_test) == TestType.MULTI_TURN

    def test_resolution_caches_the_relationship(self, multi_turn_test):
        """Resolving must leave the value cached on the instance.

        get_test_type looks the type up with sess.get(TypeLookup, ...) rather than
        touching the relationship, so it has to populate it explicitly. Without
        that, nothing is cached and a later detached read finds no session.
        """
        get_test_type(multi_turn_test)
        assert "test_type" not in sa_inspect(multi_turn_test).unloaded

    def test_detached_instance_still_resolves_multi_turn(self, multi_turn_test, test_db: Session):
        """The batch path's exact sequence: resolve, expunge, resolve again.

        Regression: this returned Single-Turn, routing Multi-Turn tests through
        SingleTurnTestExecutor with an empty prompt.
        """
        assert get_test_type(multi_turn_test) == TestType.MULTI_TURN

        test_db.expunge(multi_turn_test)

        assert get_test_type(multi_turn_test) == TestType.MULTI_TURN
