"""Every write path that decides a test result's outcome, now routed
through the single classifier in app/outcomes.py. Built up across the
migration of each of the seven duplicated implementations documented in
playground/outcome-model/inventory.md section 4.1 -- each covers the
outcome (execution/verdict columns + the legacy status name) its own
call site actually produces, not the classifier's internal rules (already
pinned in test_outcomes.py).
"""

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.utils.crud_utils import get_or_create_status


@pytest.fixture
def outcome_writer_setup(test_db: Session, test_organization, db_user, db_endpoint, db_status):
    """Enough of a real test/config/run to call create_test_result_record
    directly, without dragging in the full execution pipeline.
    """
    org_id = test_organization.id
    user_id = db_user.id

    test_config = models.TestConfiguration(
        endpoint_id=db_endpoint.id, organization_id=org_id, user_id=user_id
    )
    test_db.add(test_config)
    test_db.flush()

    test_run = models.TestRun(
        name="Outcome Writer Run",
        user_id=user_id,
        organization_id=org_id,
        status_id=db_status.id,
        test_configuration_id=test_config.id,
    )
    test_db.add(test_run)
    test_db.flush()

    test = models.Test(user_id=user_id, organization_id=org_id, prompt_id=None)
    test_db.add(test)
    test_db.flush()
    test_db.commit()

    return {
        "db": test_db,
        "test": test,
        "test_config_id": str(test_config.id),
        "test_run_id": str(test_run.id),
        "org_id": str(org_id),
        "user_id": str(user_id),
    }


@pytest.mark.unit
class TestCreateTestResultRecordOutcome:
    """jobs/execution/executors/results.py -- the main production writer."""

    def _create(self, setup, metrics_results, processed_result=None):
        from rhesis.backend.jobs.execution.executors.results import create_test_result_record

        result_id = create_test_result_record(
            db=setup["db"],
            test=setup["test"],
            test_config_id=setup["test_config_id"],
            test_run_id=setup["test_run_id"],
            test_id=str(setup["test"].id),
            organization_id=setup["org_id"],
            user_id=setup["user_id"],
            execution_time=100.0,
            metrics_results=metrics_results,
            processed_result=processed_result or {"output": "hi", "status_code": 200},
        )
        assert result_id is not None
        setup["db"].commit()
        row = setup["db"].query(models.TestResult).filter(models.TestResult.id == result_id).one()
        setup["db"].refresh(row, attribute_names=["status"])
        return row

    def test_all_metrics_passed(self, outcome_writer_setup):
        row = self._create(outcome_writer_setup, {"Accuracy": {"is_successful": True}})
        assert (row.execution, row.verdict) == ("ok", "pass")
        assert row.status.name == "Pass"

    def test_a_metric_failed(self, outcome_writer_setup):
        row = self._create(outcome_writer_setup, {"Accuracy": {"is_successful": False}})
        assert (row.execution, row.verdict) == ("ok", "fail")
        assert row.status.name == "Fail"

    def test_no_metrics(self, outcome_writer_setup):
        row = self._create(outcome_writer_setup, {})
        assert (row.execution, row.verdict) == ("error", None)
        assert row.status.name == "Error"

    def test_http_error_beats_present_metrics(self, outcome_writer_setup):
        """The HTTP-error branch is the whole reason this writer's copy of
        the rule was more careful than the other six -- a stale metrics
        dict must never paper over an endpoint that never answered.
        """
        row = self._create(
            outcome_writer_setup,
            {"Accuracy": {"is_successful": True}},
            processed_result={"output": {}, "status_code": 500, "error": "Internal error"},
        )
        assert (row.execution, row.verdict) == ("error", None)
        assert row.status.name == "Error"
        # The stale metrics were dropped, not merely ignored for status.
        assert row.test_metrics["metrics"] == {}

    def test_inconclusive_metric_gets_its_own_status(self, outcome_writer_setup):
        """Previously collapsed to Fail via the old `.get('is_successful',
        False)` default -- now a distinct, correctly-labelled outcome.
        """
        row = self._create(outcome_writer_setup, {"Accuracy": {"is_successful": None}})
        assert (row.execution, row.verdict) == ("ok", "inconclusive")
        assert row.status.name == "Inconclusive"

    def test_crashed_metric_is_error_not_fail(self, outcome_writer_setup):
        """Bug 5: a metric that crashed while evaluating must not be
        indistinguishable from one that legitimately failed.
        """
        row = self._create(
            outcome_writer_setup,
            {"Accuracy": {"is_successful": False, "error": "judge model timeout"}},
        )
        assert (row.execution, row.verdict) == ("error", None)
        assert row.status.name == "Error"

    def test_reuses_the_inconclusive_status_across_orgs_without_duplicating(
        self, outcome_writer_setup
    ):
        """get_or_create_status must find the seeded 'Inconclusive' status
        rather than create a second row for the same org -- this is
        exactly the kind of duplicate the missing unique constraint would
        otherwise allow (inventory.md section 5).
        """
        db = outcome_writer_setup["db"]
        before = get_or_create_status(
            db, "Inconclusive", "TestResult", organization_id=outcome_writer_setup["org_id"]
        )
        row = self._create(outcome_writer_setup, {"Accuracy": {"is_successful": None}})
        assert row.status_id == before.id


@pytest.mark.unit
class TestTestResultRouterOutcome:
    """routers/test_result.py's create/update -- the only write paths that
    let a caller supply status_id directly with no metrics attached at all,
    which is why execution_verdict_from_status_name exists.
    """

    def _base_result(self, setup):
        from rhesis.backend.app import schemas

        return schemas.TestResultCreate(
            test_configuration_id=setup["test_config_id"],
            test_run_id=setup["test_run_id"],
            test_id=str(setup["test"].id),
            user_id=setup["user_id"],
            organization_id=setup["org_id"],
        )

    def test_create_derives_from_metrics_when_no_status_given(self, outcome_writer_setup):
        from rhesis.backend.app.routers.test_result import create_test_result

        payload = self._base_result(outcome_writer_setup)
        payload.test_metrics = {"metrics": {"Accuracy": {"is_successful": True}}}

        row = create_test_result(
            test_result=payload,
            db=outcome_writer_setup["db"],
            tenant_context=(outcome_writer_setup["org_id"], outcome_writer_setup["user_id"]),
            current_user=type("U", (), {"id": outcome_writer_setup["user_id"]})(),
        )
        outcome_writer_setup["db"].commit()
        assert (row.execution, row.verdict) == ("ok", "pass")

    def test_create_derives_from_explicit_status_id_with_no_metrics(self, outcome_writer_setup):
        """A caller (e.g. a bulk import) supplies status_id directly --
        execution/verdict must still end up populated, from the status
        name it points to, not left at the 'not_run' default.
        """
        from rhesis.backend.app.routers.test_result import create_test_result

        fail_status = get_or_create_status(
            outcome_writer_setup["db"],
            "Fail",
            "TestResult",
            organization_id=outcome_writer_setup["org_id"],
        )
        payload = self._base_result(outcome_writer_setup)
        payload.status_id = fail_status.id

        row = create_test_result(
            test_result=payload,
            db=outcome_writer_setup["db"],
            tenant_context=(outcome_writer_setup["org_id"], outcome_writer_setup["user_id"]),
            current_user=type("U", (), {"id": outcome_writer_setup["user_id"]})(),
        )
        outcome_writer_setup["db"].commit()
        assert (row.execution, row.verdict) == ("ok", "fail")

    def test_update_derives_from_new_status_id(self, outcome_writer_setup):
        from unittest.mock import patch

        from rhesis.backend.app import schemas
        from rhesis.backend.app.routers.test_result import create_test_result, update_test_result

        payload = self._base_result(outcome_writer_setup)
        payload.test_metrics = {"metrics": {"Accuracy": {"is_successful": True}}}
        current_user = type("U", (), {"id": outcome_writer_setup["user_id"]})()
        row = create_test_result(
            test_result=payload,
            db=outcome_writer_setup["db"],
            tenant_context=(outcome_writer_setup["org_id"], outcome_writer_setup["user_id"]),
            current_user=current_user,
        )
        outcome_writer_setup["db"].commit()
        assert (row.execution, row.verdict) == ("ok", "pass")

        error_status = get_or_create_status(
            outcome_writer_setup["db"],
            "Error",
            "TestResult",
            organization_id=outcome_writer_setup["org_id"],
        )
        update_payload = schemas.TestResultUpdate(status_id=error_status.id)

        class _Request:
            headers = {}
            url = type("U", (), {"path": "/test_results/x"})()

        with (
            patch("rhesis.backend.app.routers.test_result.resolve_principal_from_request"),
            patch(
                "rhesis.backend.app.routers.test_result.project_id_from_scope", return_value=None
            ),
            patch("rhesis.backend.app.routers.test_result.authorize_object", return_value=True),
        ):
            updated = update_test_result(
                test_result_id=row.id,
                test_result=update_payload,
                request=_Request(),
                db=outcome_writer_setup["db"],
                tenant_context=(outcome_writer_setup["org_id"], outcome_writer_setup["user_id"]),
                current_user=current_user,
            )
        outcome_writer_setup["db"].commit()
        outcome_writer_setup["db"].refresh(updated)
        assert (updated.execution, updated.verdict) == ("error", None)
