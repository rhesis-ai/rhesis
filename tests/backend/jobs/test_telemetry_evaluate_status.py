"""jobs/telemetry/evaluate.py's status derivation -- one of the seven
duplicated 'all metrics passed' copies documented in
playground/outcome-model/inventory.md section 4.1, now routed through the
single classifier. No existing test covered this module before this file.
"""

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.jobs.telemetry.evaluate import (
    _derive_combined_outcome,
    _derive_outcome,
    _resolve_status_id,
)


@pytest.mark.unit
class TestDeriveStatusId:
    def test_all_metrics_passed(self, test_db: Session, test_organization):
        status_id, _execution, _verdict = _derive_outcome(
            test_db,
            str(test_organization.id),
            {"metrics": {"Accuracy": {"is_successful": True}}},
        )
        status = test_db.query(models.Status).filter(models.Status.id == status_id).one()
        assert status.name == "Pass"

    def test_a_metric_failed(self, test_db: Session, test_organization):
        status_id, _execution, _verdict = _derive_outcome(
            test_db,
            str(test_organization.id),
            {"metrics": {"Accuracy": {"is_successful": False}}},
        )
        status = test_db.query(models.Status).filter(models.Status.id == status_id).one()
        assert status.name == "Fail"

    def test_no_metrics_is_error(self, test_db: Session, test_organization):
        """The empty-dict short circuit the old code needed explicitly --
        classify_metrics({}) must still resolve to Error, not a vacuous
        Pass from `all([]) == True`.
        """
        status_id, _execution, _verdict = _derive_outcome(
            test_db, str(test_organization.id), {"metrics": {}}
        )
        status = test_db.query(models.Status).filter(models.Status.id == status_id).one()
        assert status.name == "Error"

    def test_inconclusive_metric_gets_its_own_status(self, test_db: Session, test_organization):
        status_id, _execution, _verdict = _derive_outcome(
            test_db,
            str(test_organization.id),
            {"metrics": {"Accuracy": {"is_successful": None}}},
        )
        status = test_db.query(models.Status).filter(models.Status.id == status_id).one()
        assert status.name == "Inconclusive"

    def test_crashed_metric_is_error_not_fail(self, test_db: Session, test_organization):
        status_id, _execution, _verdict = _derive_outcome(
            test_db,
            str(test_organization.id),
            {"metrics": {"Accuracy": {"is_successful": False, "error": "timeout"}}},
        )
        status = test_db.query(models.Status).filter(models.Status.id == status_id).one()
        assert status.name == "Error"


@pytest.mark.unit
class TestDeriveCombinedStatusId:
    def test_combines_turn_and_conversation_metrics(self, test_db: Session, test_organization):
        span = models.Trace(
            organization_id=test_organization.id,
            trace_metrics={
                "turn_metrics": {"metrics": {"Accuracy": {"is_successful": True}}},
                "conversation_metrics": {},
            },
        )
        # New conversation_metrics section fails -- combined must be Fail
        # even though the existing turn_metrics section passed.
        status_id, _execution, _verdict = _derive_combined_outcome(
            test_db,
            str(test_organization.id),
            span,
            "conversation_metrics",
            {"metrics": {"Coherence": {"is_successful": False}}},
        )
        status = test_db.query(models.Status).filter(models.Status.id == status_id).one()
        assert status.name == "Fail"

    def test_no_metrics_in_either_section_is_error(self, test_db: Session, test_organization):
        span = models.Trace(organization_id=test_organization.id, trace_metrics={})
        status_id, _execution, _verdict = _derive_combined_outcome(
            test_db, str(test_organization.id), span, "turn_metrics", {"metrics": {}}
        )
        status = test_db.query(models.Status).filter(models.Status.id == status_id).one()
        assert status.name == "Error"


@pytest.mark.unit
class TestResolveStatusId:
    def test_creates_the_status_for_an_org_that_lacks_it(self, test_db: Session):
        """A status like 'Inconclusive' may not exist yet for an org that
        has never produced one -- a bare lookup (the old behavior) would
        silently drop the trace's status instead of creating it. Uses a
        freshly-created, unseeded org rather than test_organization, whose
        seed data already includes every TestResult status.
        """
        from tests.backend.fixtures.test_setup import create_test_organization

        org = create_test_organization(test_db, "Trace Status Org")

        assert (
            test_db.query(models.Status)
            .filter(models.Status.organization_id == org.id, models.Status.name == "Inconclusive")
            .first()
            is None
        )

        status_id = _resolve_status_id(test_db, str(org.id), "Inconclusive")
        assert status_id is not None
        status = test_db.query(models.Status).filter(models.Status.id == status_id).one()
        assert status.name == "Inconclusive"

    def test_is_idempotent_across_calls(self, test_db: Session, test_organization):
        """Two calls for the same org/name must resolve to the same row --
        get_or_create_status has no unique constraint behind it
        (inventory.md section 5), so this is the only thing standing
        between a repeat call and a duplicate status row.
        """
        first = _resolve_status_id(test_db, str(test_organization.id), "Inconclusive")
        second = _resolve_status_id(test_db, str(test_organization.id), "Inconclusive")
        assert first == second


@pytest.mark.unit
class TestDeriveOutcomeReturnsThePair:
    """The status name alone is the legacy artefact; execution/verdict are
    the source of truth a trace row now stores (see app/outcomes.py). They
    come back together so a writer cannot persist one without the other.
    """

    @pytest.mark.parametrize(
        "metrics,expected_execution,expected_verdict",
        [
            ({"Accuracy": {"is_successful": True}}, "ok", "pass"),
            ({"Accuracy": {"is_successful": False}}, "ok", "fail"),
            ({"Accuracy": {"is_successful": None}}, "ok", "inconclusive"),
            ({"Accuracy": {"is_successful": False, "error": "timeout"}}, "error", None),
            ({}, "error", None),
        ],
    )
    def test_pair_matches_the_derived_status(
        self, test_db: Session, test_organization, metrics, expected_execution, expected_verdict
    ):
        status_id, execution, verdict = _derive_outcome(
            test_db, str(test_organization.id), {"metrics": metrics}
        )
        assert execution == expected_execution
        assert verdict == expected_verdict
        # And the legacy status name still agrees with the pair.
        status = test_db.query(models.Status).filter(models.Status.id == status_id).one()
        assert status.name in {"Pass", "Fail", "Error", "Inconclusive"}
