"""Integration tests for annotating what a metric said about its own tuning cases.

Tests the two judgement endpoints:
- POST /metrics/{metric_id}/tuning/cases/{case_id}/annotate
- POST /metrics/{metric_id}/tuning/annotations/accept-rest

A case carries no expected verdict. After a run the reviewer accepts what the
metric said or rejects it with a comment, and those comments are what someone
reads when rewriting an evaluation prompt — so most of what is asserted here is
about not losing them: a rejection cannot be recorded without one, and a
re-judgement appends a row rather than overwriting the one before it. The ten-slot
cap and the evict-accepts rule the JSONB history needed are gone with it — a table
has no budget to spend — so what replaces those cases is "the newest stands and
the history is kept". See domain.local/adr/0005.

Each judgement is an ``annotation`` row on the case: ``(Test, metric)`` with the
metric's id as the reference, the decision as the status, and the verdict it
judged in ``attributes``. The stored-state assertions read those rows directly,
because the API only ever exposes the one that currently stands.

The metric invocation is stubbed throughout, which is what makes these
deterministic and free of LLM calls. Runs are driven by calling the service the
background task would have called, rather than by running a broker.

Run with: python -m pytest tests/backend/routes/test_metric_tuning_annotations.py -v
"""

import uuid
from typing import List
from unittest.mock import MagicMock, patch

import pytest
import sqlalchemy as sa
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, joinedload

from rhesis.backend.app import models
from rhesis.backend.app.schemas.metric import MetricScope
from rhesis.backend.app.services import metric_tuning as service
from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup

CASE_INPUT = "How are you?"
CASE_OUTPUT = "I am fine you fucking basterd"
CASE_REFERENCE_ANSWER = "I am fine, thanks for asking."
ANNOTATION_COMMENT = "the metric scored this as harmless, but it is plainly toxic"


def _make_model(db: Session, organization_id, user_id) -> models.Model:
    """A judging model for the metric to point at, so a run is not refused."""
    provider_lookup = get_or_create_type_lookup(
        db=db,
        type_name="ProviderType",
        type_value="openai",
        organization_id=organization_id,
        user_id=user_id,
        commit=False,
    )
    model = models.Model(
        name=f"Judge {uuid.uuid4().hex[:6]}",
        model_name="gpt-4o-mini",
        key="sk-not-a-real-key",
        provider_type_id=provider_lookup.id,
        organization_id=organization_id,
        user_id=user_id,
    )
    db.add(model)
    db.flush()
    return model


def _make_metric(
    db: Session,
    name: str,
    organization_id,
    user_id,
    *,
    score_type: str = "binary",
    backend_type: str = "custom",
    **columns,
) -> models.Metric:
    backend_type_lookup = get_or_create_type_lookup(
        db=db,
        type_name="BackendType",
        type_value=backend_type,
        organization_id=organization_id,
        user_id=user_id,
        commit=False,
    )
    model = _make_model(db, organization_id, user_id)
    metric = models.Metric(
        name=name,
        description="Metric under tuning",
        evaluation_prompt="Score how toxic the answer is.",
        score_type=score_type,
        metric_scope=[MetricScope.SINGLE_TURN.value],
        backend_type_id=backend_type_lookup.id,
        model_id=model.id,
        organization_id=organization_id,
        user_id=user_id,
        **columns,
    )
    db.add(metric)
    db.flush()
    db.commit()
    db.refresh(metric)
    return metric


@pytest.fixture
def tuning_metric(test_db: Session, test_org_id, authenticated_user_id) -> models.Metric:
    """A binary custom metric with no tuning test set yet."""
    return _make_metric(
        test_db, f"Toxicity Annotate {uuid.uuid4().hex[:6]}", test_org_id, authenticated_user_id
    )


@pytest.fixture
def numeric_metric(test_db: Session, test_org_id, authenticated_user_id) -> models.Metric:
    """A numeric metric whose threshold is what decides whether a judgement stands."""
    return _make_metric(
        test_db,
        f"Numeric Annotate {uuid.uuid4().hex[:6]}",
        test_org_id,
        authenticated_user_id,
        score_type="numeric",
        min_score=0.0,
        max_score=1.0,
        threshold=0.5,
        threshold_operator=">=",
    )


@pytest.fixture
def other_metric(test_db: Session, test_org_id, authenticated_user_id) -> models.Metric:
    """A second custom metric, with its own tuning set."""
    return _make_metric(
        test_db, f"Other Annotate {uuid.uuid4().hex[:6]}", test_org_id, authenticated_user_id
    )


@pytest.fixture
def framework_metric(test_db: Session, test_org_id, authenticated_user_id) -> models.Metric:
    """A framework-provided metric — its prompt is not the org's to tune."""
    return _make_metric(
        test_db,
        f"Framework Annotate {uuid.uuid4().hex[:6]}",
        test_org_id,
        authenticated_user_id,
        backend_type="deepeval",
    )


def _create_case(client: TestClient, metric_id, **overrides) -> dict:
    body = {
        "input": CASE_INPUT,
        "output": CASE_OUTPUT,
        "reference_answer": CASE_REFERENCE_ANSWER,
    }
    body.update(overrides)
    response = client.post(f"/metrics/{metric_id}/tuning/cases", json=body)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


def _evaluator_returning(*results, by_input=None):
    """A stubbed MetricEvaluator whose evaluate() yields the given results in order.

    Each entry is either a result dict or an exception to raise. ``by_input``
    keys the results on the case's input instead of on call order, which is the
    only way to land a particular result on a particular case: the run walks the
    cases in list order, and that is not insertion order — every case created
    inside one test shares a ``created_at``, so the list comes back sorted by id.
    """
    calls = list(results)
    evaluator = MagicMock()

    def _evaluate(**kwargs):
        if by_input is not None:
            outcome = by_input[kwargs["input_text"]]
        else:
            outcome = calls.pop(0) if calls else {"score": 0.0, "reason": "no more stubs"}
        if isinstance(outcome, Exception):
            raise outcome
        return {"Metric": outcome}

    evaluator.evaluate.side_effect = _evaluate
    return MagicMock(return_value=evaluator), evaluator


def _run(db: Session, metric: models.Metric, org_id, *results, by_input=None):
    """Execute a run with the metric invocation stubbed.

    ``by_input`` keys the stubbed results on the case's input — see
    ``_evaluator_returning``.

    Expires the session first because the judgements these tests are about were
    written by a request on its own session. Without it this session serves the
    rows it cached before that commit, and the run rewrites them from stale
    metadata — a background worker always starts from a fresh session.
    """
    db.expire_all()
    factory, evaluator = _evaluator_returning(*results, by_input=by_input)
    with patch("rhesis.backend.metrics.evaluator.MetricEvaluator", factory):
        service.execute_tuning_run(db, metric, org_id, None)
    return evaluator


def _annotate(client: TestClient, metric_id, case_id, decision: str, comment=None):
    body = {"decision": decision}
    if comment is not None:
        body["comment"] = comment
    return client.post(f"/metrics/{metric_id}/tuning/cases/{case_id}/annotate", json=body)


def _accepted(client: TestClient, metric_id, case_id) -> dict:
    response = _annotate(client, metric_id, case_id, "accepted")
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


def _rejected(client: TestClient, metric_id, case_id, comment: str = ANNOTATION_COMMENT) -> dict:
    response = _annotate(client, metric_id, case_id, "rejected", comment)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


def _stored(db: Session, case_id, metric_id=None) -> List[models.Annotation]:
    """The case's judgement rows as they sit in the table, oldest first.

    Read directly rather than through the API because the API only exposes the
    judgement that currently stands — appending and standing-ness are both about
    the whole list. Filtered to metric targets so an entity-level annotation
    somebody left on the same row is not mistaken for a judgement of the metric.
    """
    db.expire_all()
    query = (
        db.query(models.Annotation)
        .options(joinedload(models.Annotation.status))
        .filter(
            models.Annotation.entity_type == "Test",
            models.Annotation.entity_id == uuid.UUID(str(case_id)),
            models.Annotation.target_type == "metric",
            models.Annotation.deleted_at.is_(None),
        )
    )
    if metric_id is not None:
        query = query.filter(models.Annotation.target_reference == str(metric_id))
    return query.order_by(models.Annotation.created_at.asc()).all()


def _decisions(annotations: List[models.Annotation]) -> List[str]:
    """The decision each stored row records, read off its status as the service does."""
    return [annotation.status.name.lower() for annotation in annotations]


def _separate_in_time(db: Session, case_id) -> None:
    """Push the case's existing judgements a second into the past.

    Every request in a test shares one transaction, so Postgres stamps every row
    it inserts with the same ``now()``. The id tie-break in
    ``get_annotations_for_entities`` makes which row comes back first *stable*,
    but not the last-written one — there is no write-order column to ask. So a
    test about "the newest judgement stands" has to space the writes the way
    production does, where each one is its own transaction landing a moment after
    the last. Tests that only count rows do not need this.
    """
    db.execute(
        sa.text(
            "UPDATE annotation"
            " SET created_at = created_at - interval '1 second',"
            "     updated_at = updated_at - interval '1 second'"
            " WHERE entity_type = 'Test' AND entity_id = CAST(:case_id AS uuid)"
        ),
        {"case_id": str(case_id)},
    )
    db.flush()
    db.expire_all()


def _prompt(db: Session, case_id) -> models.Prompt:
    """The case's prompt row — what the metric is actually shown."""
    db.expire_all()
    db_test = (
        db.query(models.Test)
        .options(joinedload(models.Test.prompt))
        .filter(models.Test.id == uuid.UUID(str(case_id)))
        .first()
    )
    return db_test.prompt


def _cases(client: TestClient, metric_id) -> List[dict]:
    response = client.get(f"/metrics/{metric_id}/tuning/cases")
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


def _by_id(cases: List[dict]) -> dict:
    """Cases keyed by their own id, because a list position is not a case.

    The list is ordered by ``created_at`` then id, and every case created inside
    one test shares a ``created_at`` — so it sorts by id, not by insertion.
    """
    return {case["id"]: case for case in cases}


@pytest.mark.integration
class TestTheFourOutcomes:
    """Every outcome is reachable, and each one reports itself rather than another."""

    def test_a_case_nobody_has_judged_is_unannotated(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "harmless"})

        case = _cases(authenticated_client, tuning_metric.id)[0]

        assert case["outcome"] == "unannotated"
        assert case["annotation"] is None
        assert case["unannotated_reason"] == "never_judged"

    def test_an_accepted_case_reports_the_verdict_it_agreed_with(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        case = _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, {"score": 0.0, "reason": "toxic"})

        body = _accepted(authenticated_client, tuning_metric.id, case["id"])

        assert body["outcome"] == "accepted"
        assert body["annotation"]["decision"] == "accepted"
        assert body["annotation"]["verdict"] == "fail"
        assert body["annotation"]["comment"] is None
        assert body["annotation"]["annotated_at"]
        assert body["annotation"]["id"]
        assert body["unannotated_reason"] is None

    def test_a_rejected_case_carries_the_comment(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        case = _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "harmless"})

        body = _rejected(authenticated_client, tuning_metric.id, case["id"])

        assert body["outcome"] == "rejected"
        assert body["annotation"]["decision"] == "rejected"
        assert body["annotation"]["comment"] == ANNOTATION_COMMENT
        assert body["unannotated_reason"] is None

    def test_a_failed_metric_call_is_errored_not_rejected(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """A flaky provider is not a metric a reviewer disagreed with."""
        _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, RuntimeError("provider unreachable"))

        case = _cases(authenticated_client, tuning_metric.id)[0]

        assert case["outcome"] == "errored"
        assert case["annotation"] is None
        assert case["unannotated_reason"] is None


@pytest.mark.integration
class TestWhereAJudgementIsStored:
    """The row itself: what it targets, what it carries, and who it belongs to."""

    def test_it_is_an_annotation_on_the_case_targeting_the_metric(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
        authenticated_user_id,
    ):
        case = _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "harmless"})

        _rejected(authenticated_client, tuning_metric.id, case["id"])

        stored = _stored(test_db, case["id"], tuning_metric.id)
        assert len(stored) == 1
        annotation = stored[0]
        assert annotation.entity_type == "Test"
        assert str(annotation.entity_id) == case["id"]
        assert annotation.target_type == "metric"
        # The id, not the name: a renamed metric must not lose its judgements.
        assert annotation.target_reference == str(tuning_metric.id)
        assert annotation.status.name == "Rejected"
        assert annotation.comments == ANNOTATION_COMMENT
        assert str(annotation.user_id) == str(authenticated_user_id)

    def test_it_records_the_verdict_and_score_type_it_judged(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        numeric_metric: models.Metric,
    ):
        """The raw verdict, not the bucket — the bucket is derived from the
        metric's current threshold on every read. The score type travels with it
        because a judgement means something else under a different one."""
        case = _create_case(authenticated_client, numeric_metric.id)
        _run(test_db, numeric_metric, test_org_id, {"score": 0.79, "reason": "close enough"})

        body = _rejected(authenticated_client, numeric_metric.id, case["id"])

        assert body["annotation"]["verdict"] == "0.79"
        annotation = _stored(test_db, case["id"], numeric_metric.id)[0]
        assert annotation.attributes == {"verdict": "0.79", "score_type": "numeric"}

    def test_an_accept_carries_no_comment_at_all(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """Blank is stored as absent, so "has a comment" is one check everywhere."""
        case = _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, {"score": 0.0, "reason": "toxic"})

        _accepted(authenticated_client, tuning_metric.id, case["id"])

        assert _stored(test_db, case["id"], tuning_metric.id)[0].comments is None

    def test_another_metric_judging_the_same_case_keeps_the_two_apart(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
        other_metric: models.Metric,
    ):
        """The target reference is what separates them, so neither reads the
        other's judgement as its own."""
        mine = _create_case(authenticated_client, tuning_metric.id)
        theirs = _create_case(authenticated_client, other_metric.id, input="Their case")
        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "harmless"})
        _run(test_db, other_metric, test_org_id, {"score": 1.0, "reason": "harmless"})

        _rejected(authenticated_client, tuning_metric.id, mine["id"])
        _accepted(authenticated_client, other_metric.id, theirs["id"])

        assert _decisions(_stored(test_db, mine["id"], tuning_metric.id)) == ["rejected"]
        assert _stored(test_db, mine["id"], other_metric.id) == []
        assert _decisions(_stored(test_db, theirs["id"], other_metric.id)) == ["accepted"]


@pytest.mark.integration
class TestARejectionNeedsAComment:
    """The comment is the thing the feature produces, so a rejection without one
    records nothing worth keeping."""

    def test_a_rejection_with_no_comment_is_refused(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        case = _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "harmless"})

        response = _annotate(authenticated_client, tuning_metric.id, case["id"], "rejected")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "comment" in response.json()["detail"].lower()
        assert _stored(test_db, case["id"]) == []

    def test_a_rejection_with_a_blank_comment_is_refused(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """Whitespace is not a reason, so it is refused like an absent comment."""
        case = _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "harmless"})

        response = _annotate(authenticated_client, tuning_metric.id, case["id"], "rejected", "   ")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert _stored(test_db, case["id"]) == []
        assert _cases(authenticated_client, tuning_metric.id)[0]["outcome"] == "unannotated"

    def test_an_accept_needs_no_comment(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """Agreeing is one click — there is nothing to explain."""
        case = _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, {"score": 0.0, "reason": "toxic"})

        response = _annotate(authenticated_client, tuning_metric.id, case["id"], "accepted")

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["annotation"]["comment"] is None


@pytest.mark.integration
class TestAnnotatingOneCase:
    """POST /metrics/{metric_id}/tuning/cases/{case_id}/annotate"""

    def test_accepting_one_case_leaves_the_others_unannotated(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """A per-row accept judges that row and nothing else."""
        first = _create_case(authenticated_client, tuning_metric.id)
        second = _create_case(authenticated_client, tuning_metric.id, input="The second one")
        _run(
            test_db,
            tuning_metric,
            test_org_id,
            by_input={
                CASE_INPUT: {"score": 0.0, "reason": "toxic"},
                "The second one": {"score": 1.0, "reason": "harmless"},
            },
        )

        _accepted(authenticated_client, tuning_metric.id, first["id"])

        cases = _by_id(_cases(authenticated_client, tuning_metric.id))
        assert cases[first["id"]]["outcome"] == "accepted"
        assert cases[second["id"]]["outcome"] == "unannotated"
        assert cases[second["id"]]["unannotated_reason"] == "never_judged"

    def test_a_case_with_no_verdict_cannot_be_annotated(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        """Nothing has been said about it yet, so there is nothing to judge."""
        case = _create_case(authenticated_client, tuning_metric.id)

        response = _annotate(authenticated_client, tuning_metric.id, case["id"], "accepted")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "verdict" in response.json()["detail"].lower()
        assert _stored(test_db, case["id"]) == []

    def test_a_case_whose_metric_call_failed_cannot_be_annotated(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """An unreachable provider left no judgement to agree or disagree with."""
        case = _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, RuntimeError("provider unreachable"))

        response = _annotate(authenticated_client, tuning_metric.id, case["id"], "accepted")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert _stored(test_db, case["id"]) == []

    def test_a_case_from_another_metric_404s(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
        other_metric: models.Metric,
    ):
        """The membership join is the authorization check."""
        _create_case(authenticated_client, tuning_metric.id)
        theirs = _create_case(authenticated_client, other_metric.id, input="Their case")
        _run(test_db, other_metric, test_org_id, {"score": 1.0, "reason": "harmless"})

        response = _annotate(authenticated_client, tuning_metric.id, theirs["id"], "accepted")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert _stored(test_db, theirs["id"]) == []

    def test_an_unknown_case_404s(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        _create_case(authenticated_client, tuning_metric.id)

        response = _annotate(authenticated_client, tuning_metric.id, uuid.uuid4(), "accepted")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_a_framework_metric_cannot_be_annotated(
        self, authenticated_client: TestClient, framework_metric: models.Metric
    ):
        """Refused in the API, not only by hiding the tab."""
        response = _annotate(authenticated_client, framework_metric.id, uuid.uuid4(), "accepted")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "custom" in response.json()["detail"].lower()

    def test_an_unknown_metric_404s(self, authenticated_client: TestClient):
        response = _annotate(authenticated_client, uuid.uuid4(), uuid.uuid4(), "accepted")

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
class TestAcceptTheRest:
    """POST /metrics/{metric_id}/tuning/annotations/accept-rest"""

    def _accept_rest(self, client: TestClient, metric_id) -> List[dict]:
        response = client.post(f"/metrics/{metric_id}/tuning/annotations/accept-rest")
        assert response.status_code == status.HTTP_200_OK, response.text
        return response.json()

    def test_accepts_every_unannotated_case_that_has_a_verdict(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """What stops forty cases becoming forty decisions."""
        _create_case(authenticated_client, tuning_metric.id)
        _create_case(authenticated_client, tuning_metric.id, input="The second one")
        _create_case(authenticated_client, tuning_metric.id, input="The third one")
        _run(
            test_db,
            tuning_metric,
            test_org_id,
            {"score": 0.0, "reason": "toxic"},
            {"score": 1.0, "reason": "harmless"},
            {"score": 0.0, "reason": "toxic too"},
        )

        cases = self._accept_rest(authenticated_client, tuning_metric.id)

        assert len(cases) == 3
        assert {case["outcome"] for case in cases} == {"accepted"}
        assert all(case["annotation"]["comment"] is None for case in cases)

    def test_an_already_rejected_case_is_left_as_it_was(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """It is *the rest* — a judgement already made is not joined by an accept."""
        rejected = _create_case(authenticated_client, tuning_metric.id)
        other = _create_case(authenticated_client, tuning_metric.id, input="The second one")
        _run(
            test_db,
            tuning_metric,
            test_org_id,
            by_input={
                CASE_INPUT: {"score": 1.0, "reason": "harmless"},
                "The second one": {"score": 0.0, "reason": "toxic"},
            },
        )
        _rejected(authenticated_client, tuning_metric.id, rejected["id"])

        cases = _by_id(self._accept_rest(authenticated_client, tuning_metric.id))

        assert cases[rejected["id"]]["outcome"] == "rejected"
        assert cases[rejected["id"]]["annotation"]["comment"] == ANNOTATION_COMMENT
        assert cases[other["id"]]["outcome"] == "accepted"
        # One row each: the rejection was not joined by an accept behind it.
        assert _decisions(_stored(test_db, rejected["id"], tuning_metric.id)) == ["rejected"]

    def test_an_errored_case_stays_unannotated(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """There is no verdict to agree with, so accepting it would mean nothing."""
        errored = _create_case(authenticated_client, tuning_metric.id)
        judged = _create_case(authenticated_client, tuning_metric.id, input="The second one")
        _run(
            test_db,
            tuning_metric,
            test_org_id,
            by_input={
                CASE_INPUT: RuntimeError("provider unreachable"),
                "The second one": {"score": 1.0, "reason": "harmless"},
            },
        )

        cases = _by_id(self._accept_rest(authenticated_client, tuning_metric.id))

        assert cases[errored["id"]]["outcome"] == "errored"
        assert cases[errored["id"]]["annotation"] is None
        assert _stored(test_db, errored["id"]) == []
        assert cases[judged["id"]]["outcome"] == "accepted"

    def test_a_case_never_run_stays_unannotated(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        ran = _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "harmless"})
        fresh = _create_case(authenticated_client, tuning_metric.id, input="Added after the run")

        cases = _by_id(self._accept_rest(authenticated_client, tuning_metric.id))

        assert cases[ran["id"]]["outcome"] == "accepted"
        assert cases[fresh["id"]]["outcome"] == "unannotated"
        assert cases[fresh["id"]]["unannotated_reason"] == "never_judged"
        assert _stored(test_db, fresh["id"]) == []

    def test_a_metric_with_no_cases_returns_an_empty_list(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        assert self._accept_rest(authenticated_client, tuning_metric.id) == []

    def test_a_framework_metric_cannot_be_accepted(
        self, authenticated_client: TestClient, framework_metric: models.Metric
    ):
        response = authenticated_client.post(
            f"/metrics/{framework_metric.id}/tuning/annotations/accept-rest"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "custom" in response.json()["detail"].lower()

    def test_an_unknown_metric_404s(self, authenticated_client: TestClient):
        response = authenticated_client.post(
            f"/metrics/{uuid.uuid4()}/tuning/annotations/accept-rest"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
class TestAnnotationHistory:
    """Rows are append-only and the newest standing one wins.

    This is what replaced the JSONB history's replace-and-evict rules. A table
    has no ten-slot budget to spend, so a mis-click costs nothing, no comment can
    ever be dropped to make room for one, and every judgement anybody made stays
    readable.
    """

    def test_re_judging_a_case_appends_and_the_newest_stands(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        case = _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "harmless"})

        _accepted(authenticated_client, tuning_metric.id, case["id"])
        _separate_in_time(test_db, case["id"])
        body = _rejected(authenticated_client, tuning_metric.id, case["id"])

        assert body["outcome"] == "rejected"
        assert body["annotation"]["comment"] == ANNOTATION_COMMENT
        stored = _stored(test_db, case["id"], tuning_metric.id)
        assert _decisions(stored) == ["accepted", "rejected"], "the accept is kept as history"

    def test_the_standing_judgement_is_the_newest_not_the_first(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """Three judgements deep, the API still reports only the last one."""
        case = _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "harmless"})

        _rejected(authenticated_client, tuning_metric.id, case["id"], "first look")
        _separate_in_time(test_db, case["id"])
        _rejected(authenticated_client, tuning_metric.id, case["id"], "second look")
        _separate_in_time(test_db, case["id"])
        body = _accepted(authenticated_client, tuning_metric.id, case["id"])

        assert body["outcome"] == "accepted"
        assert body["annotation"]["comment"] is None
        stored = _stored(test_db, case["id"], tuning_metric.id)
        assert _decisions(stored) == ["rejected", "rejected", "accepted"]
        assert [row.comments for row in stored] == ["first look", "second look", None]

    def test_a_judgement_of_a_materially_different_verdict_is_also_appended(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        numeric_metric: models.Metric,
    ):
        """Appending is now the only behaviour, whether the verdict moved or not."""
        case = _create_case(authenticated_client, numeric_metric.id)
        _run(test_db, numeric_metric, test_org_id, {"score": 0.79, "reason": "over the line"})
        _accepted(authenticated_client, numeric_metric.id, case["id"])
        _separate_in_time(test_db, case["id"])

        _run(test_db, numeric_metric, test_org_id, {"score": 0.2, "reason": "under the line"})
        _rejected(authenticated_client, numeric_metric.id, case["id"])

        stored = _stored(test_db, case["id"], numeric_metric.id)
        assert len(stored) == 2
        assert [row.attributes["verdict"] for row in stored] == ["0.79", "0.2"]

    def test_no_amount_of_judging_drops_a_comment(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        numeric_metric: models.Metric,
    ):
        """The cap that could have dropped one is gone, so twelve comments stay
        twelve comments — that is the whole reason this moved to a table."""
        case = _create_case(authenticated_client, numeric_metric.id)
        _run(test_db, numeric_metric, test_org_id, {"score": 0.9, "reason": "run 0"})
        _accepted(authenticated_client, numeric_metric.id, case["id"])

        for index in range(1, 13):
            _separate_in_time(test_db, case["id"])
            _rejected(authenticated_client, numeric_metric.id, case["id"], f"wrong #{index}")

        stored = _stored(test_db, case["id"], numeric_metric.id)
        assert len(stored) == 13
        assert [row.comments for row in stored] == [None] + [
            f"wrong #{index}" for index in range(1, 13)
        ]


@pytest.mark.integration
class TestJudgementsAreInvisibleToTheMetric:
    """A scorecard has to reflect the metric's judgement, not its ability to
    read a reviewer's hint."""

    def test_annotating_does_not_change_what_the_case_shows_the_metric(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        case = _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "harmless"})
        content_before = _prompt(test_db, case["id"]).content

        _rejected(authenticated_client, tuning_metric.id, case["id"])

        prompt = _prompt(test_db, case["id"])
        assert prompt.content == content_before
        assert ANNOTATION_COMMENT not in prompt.content
        # The column the normal evaluation path would hand the metric as a
        # reference answer stays empty for a tuning case.
        assert prompt.expected_response is None

    def test_a_run_does_not_clear_the_judgements_before_it(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """Judgements are human-authored and are not run output, so a run only
        overwrites the machine's result."""
        case = _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "harmless"})
        _rejected(authenticated_client, tuning_metric.id, case["id"])

        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "harmless again"})

        stored = _stored(test_db, case["id"], tuning_metric.id)
        assert [row.comments for row in stored] == [ANNOTATION_COMMENT]
