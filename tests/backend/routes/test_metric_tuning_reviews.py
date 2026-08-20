"""Integration tests for reviewing what a metric said about its own tuning cases.

Tests the two review endpoints:
- POST /metrics/{metric_id}/tuning/cases/{case_id}/review
- POST /metrics/{metric_id}/tuning/reviews/accept-rest

A case carries no expected verdict. After a run the reviewer accepts what the
metric said or rejects it with a comment, and those comments are what someone
reads when rewriting an evaluation prompt — so most of what is asserted here is
about not losing them: a rejection cannot be recorded without one, a re-judgement
replaces rather than appends, and the ten-review cap evicts accepts and never a
comment. See domain.local/adr/0005.

The metric invocation is stubbed throughout, which is what makes these
deterministic and free of LLM calls. Runs are driven by calling the service the
background task would have called, rather than by running a broker.

Run with: python -m pytest tests/backend/routes/test_metric_tuning_reviews.py -v
"""

import uuid
from typing import List
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, joinedload

from rhesis.backend.app import models
from rhesis.backend.app.schemas.metric import MetricScope
from rhesis.backend.app.schemas.metric_tuning_metadata import REVIEW_HISTORY_LIMIT
from rhesis.backend.app.services import metric_tuning as service
from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup

CASE_INPUT = "How are you?"
CASE_OUTPUT = "I am fine you fucking basterd"
CASE_REFERENCE_ANSWER = "I am fine, thanks for asking."
REVIEW_COMMENT = "the metric scored this as harmless, but it is plainly toxic"


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
        test_db, f"Toxicity Review {uuid.uuid4().hex[:6]}", test_org_id, authenticated_user_id
    )


@pytest.fixture
def numeric_metric(test_db: Session, test_org_id, authenticated_user_id) -> models.Metric:
    """A numeric metric whose threshold is what decides whether a review stands."""
    return _make_metric(
        test_db,
        f"Numeric Review {uuid.uuid4().hex[:6]}",
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
        test_db, f"Other Review {uuid.uuid4().hex[:6]}", test_org_id, authenticated_user_id
    )


@pytest.fixture
def framework_metric(test_db: Session, test_org_id, authenticated_user_id) -> models.Metric:
    """A framework-provided metric — its prompt is not the org's to tune."""
    return _make_metric(
        test_db,
        f"Framework Review {uuid.uuid4().hex[:6]}",
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

    Expires the session first because the reviews these tests are about were
    written by a request on its own session. Without it this session serves the
    rows it cached before that commit, and the run rewrites them from stale
    metadata — a background worker always starts from a fresh session.
    """
    db.expire_all()
    factory, evaluator = _evaluator_returning(*results, by_input=by_input)
    with patch("rhesis.backend.metrics.evaluator.MetricEvaluator", factory):
        service.execute_tuning_run(db, metric, org_id, None)
    return evaluator


def _review(client: TestClient, metric_id, case_id, decision: str, comment=None):
    body = {"decision": decision}
    if comment is not None:
        body["comment"] = comment
    return client.post(f"/metrics/{metric_id}/tuning/cases/{case_id}/review", json=body)


def _accepted(client: TestClient, metric_id, case_id) -> dict:
    response = _review(client, metric_id, case_id, "accepted")
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


def _rejected(client: TestClient, metric_id, case_id, comment: str = REVIEW_COMMENT) -> dict:
    response = _review(client, metric_id, case_id, "rejected", comment)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


def _stored_reviews(db: Session, case_id) -> List[dict]:
    """The case's review history exactly as it sits in the JSONB, oldest first.

    Read raw rather than through the API because the API only exposes the review
    that currently stands — replacement, appending and eviction are all about
    the list.
    """
    db.expire_all()
    db_test = db.query(models.Test).filter(models.Test.id == uuid.UUID(str(case_id))).first()
    return (db_test.test_metadata or {}).get("reviews", [])


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
@pytest.mark.routes
class TestTheFourOutcomes:
    """Every outcome is reachable, and each one reports itself rather than another."""

    def test_a_case_nobody_has_judged_is_unreviewed(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "harmless"})

        case = _cases(authenticated_client, tuning_metric.id)[0]

        assert case["outcome"] == "unreviewed"
        assert case["review"] is None
        assert case["unreviewed_reason"] == "never_judged"

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
        assert body["review"]["decision"] == "accepted"
        assert body["review"]["verdict"] == "fail"
        assert body["review"]["comment"] is None
        assert body["review"]["reviewed_at"]
        assert body["unreviewed_reason"] is None

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
        assert body["review"]["decision"] == "rejected"
        assert body["review"]["comment"] == REVIEW_COMMENT
        assert body["unreviewed_reason"] is None

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
        assert case["review"] is None
        assert case["unreviewed_reason"] is None


@pytest.mark.integration
@pytest.mark.routes
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

        response = _review(authenticated_client, tuning_metric.id, case["id"], "rejected")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "comment" in response.json()["detail"].lower()
        assert _stored_reviews(test_db, case["id"]) == []

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

        response = _review(authenticated_client, tuning_metric.id, case["id"], "rejected", "   ")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert _stored_reviews(test_db, case["id"]) == []
        assert _cases(authenticated_client, tuning_metric.id)[0]["outcome"] == "unreviewed"

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

        response = _review(authenticated_client, tuning_metric.id, case["id"], "accepted")

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["review"]["comment"] is None


@pytest.mark.integration
@pytest.mark.routes
class TestReviewingOneCase:
    """POST /metrics/{metric_id}/tuning/cases/{case_id}/review"""

    def test_accepting_one_case_leaves_the_others_unreviewed(
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
        assert cases[second["id"]]["outcome"] == "unreviewed"
        assert cases[second["id"]]["unreviewed_reason"] == "never_judged"

    def test_a_case_with_no_verdict_cannot_be_reviewed(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        """Nothing has been said about it yet, so there is nothing to judge."""
        case = _create_case(authenticated_client, tuning_metric.id)

        response = _review(authenticated_client, tuning_metric.id, case["id"], "accepted")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "verdict" in response.json()["detail"].lower()
        assert _stored_reviews(test_db, case["id"]) == []

    def test_a_case_whose_metric_call_failed_cannot_be_reviewed(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """An unreachable provider left no judgement to agree or disagree with."""
        case = _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, RuntimeError("provider unreachable"))

        response = _review(authenticated_client, tuning_metric.id, case["id"], "accepted")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert _stored_reviews(test_db, case["id"]) == []

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

        response = _review(authenticated_client, tuning_metric.id, theirs["id"], "accepted")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert _stored_reviews(test_db, theirs["id"]) == []

    def test_an_unknown_case_404s(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        _create_case(authenticated_client, tuning_metric.id)

        response = _review(authenticated_client, tuning_metric.id, uuid.uuid4(), "accepted")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_a_framework_metric_cannot_be_reviewed(
        self, authenticated_client: TestClient, framework_metric: models.Metric
    ):
        """Refused in the API, not only by hiding the tab."""
        response = _review(authenticated_client, framework_metric.id, uuid.uuid4(), "accepted")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "custom" in response.json()["detail"].lower()

    def test_an_unknown_metric_404s(self, authenticated_client: TestClient):
        response = _review(authenticated_client, uuid.uuid4(), uuid.uuid4(), "accepted")

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
@pytest.mark.routes
class TestAcceptTheRest:
    """POST /metrics/{metric_id}/tuning/reviews/accept-rest"""

    def _accept_rest(self, client: TestClient, metric_id) -> List[dict]:
        response = client.post(f"/metrics/{metric_id}/tuning/reviews/accept-rest")
        assert response.status_code == status.HTTP_200_OK, response.text
        return response.json()

    def test_accepts_every_unreviewed_case_that_has_a_verdict(
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
        assert all(case["review"]["comment"] is None for case in cases)

    def test_an_already_rejected_case_is_left_as_it_was(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """It is *the rest* — a judgement already made is not overwritten."""
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
        assert cases[rejected["id"]]["review"]["comment"] == REVIEW_COMMENT
        assert cases[other["id"]]["outcome"] == "accepted"
        # One review each: the rejection was not joined by an accept behind it.
        assert len(_stored_reviews(test_db, rejected["id"])) == 1

    def test_an_errored_case_stays_unreviewed(
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
        assert cases[errored["id"]]["review"] is None
        assert _stored_reviews(test_db, errored["id"]) == []
        assert cases[judged["id"]]["outcome"] == "accepted"

    def test_a_case_never_run_stays_unreviewed(
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
        assert cases[fresh["id"]]["outcome"] == "unreviewed"
        assert cases[fresh["id"]]["unreviewed_reason"] == "never_judged"
        assert _stored_reviews(test_db, fresh["id"]) == []

    def test_a_metric_with_no_cases_returns_an_empty_list(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        assert self._accept_rest(authenticated_client, tuning_metric.id) == []

    def test_a_framework_metric_cannot_be_accepted(
        self, authenticated_client: TestClient, framework_metric: models.Metric
    ):
        response = authenticated_client.post(
            f"/metrics/{framework_metric.id}/tuning/reviews/accept-rest"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "custom" in response.json()["detail"].lower()

    def test_an_unknown_metric_404s(self, authenticated_client: TestClient):
        response = authenticated_client.post(f"/metrics/{uuid.uuid4()}/tuning/reviews/accept-rest")

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
@pytest.mark.routes
class TestReviewHistory:
    """What the stored list of reviews does as judgements pile up."""

    def test_re_judging_the_same_verdict_replaces_the_last_review(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """A mis-click corrected a second later must not spend two of the ten slots."""
        case = _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "harmless"})

        _accepted(authenticated_client, tuning_metric.id, case["id"])
        body = _rejected(authenticated_client, tuning_metric.id, case["id"])

        assert body["outcome"] == "rejected"
        stored = _stored_reviews(test_db, case["id"])
        assert len(stored) == 1, "the accept was replaced, not kept alongside the rejection"
        assert stored[0]["decision"] == "rejected"
        assert stored[0]["comment"] == REVIEW_COMMENT

    def test_a_review_of_a_materially_different_verdict_is_appended(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        numeric_metric: models.Metric,
    ):
        """Replacement is only for a re-judgement of the same decision."""
        case = _create_case(authenticated_client, numeric_metric.id)
        _run(test_db, numeric_metric, test_org_id, {"score": 0.79, "reason": "over the line"})
        _accepted(authenticated_client, numeric_metric.id, case["id"])

        _run(test_db, numeric_metric, test_org_id, {"score": 0.2, "reason": "under the line"})
        _rejected(authenticated_client, numeric_metric.id, case["id"])

        stored = _stored_reviews(test_db, case["id"])
        assert len(stored) == 2
        assert [review["verdict"] for review in stored] == ["0.79", "0.2"]

    def test_a_rejection_records_the_raw_verdict_it_judged(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        numeric_metric: models.Metric,
    ):
        """The raw verdict, not the bucket — the bucket is derived from the
        metric's current threshold on every read."""
        case = _create_case(authenticated_client, numeric_metric.id)
        _run(test_db, numeric_metric, test_org_id, {"score": 0.79, "reason": "close enough"})

        body = _rejected(authenticated_client, numeric_metric.id, case["id"])

        assert body["review"]["verdict"] == "0.79"
        stored = _stored_reviews(test_db, case["id"])
        assert stored[0]["verdict"] == "0.79"
        assert stored[0]["score_type"] == "numeric"
        assert stored[0]["comment"] == REVIEW_COMMENT

    def _push_reviews(self, client: TestClient, db: Session, metric, org_id, case_id, count: int):
        """Record ``count`` reviews on one case, one per run.

        Each run lands on the other side of the metric's threshold from the last,
        so every review judges a materially different verdict and appends instead
        of replacing the one before it. The first is an accept — the only kind of
        review the cap is allowed to evict — and the rest carry comments.
        """
        for index in range(count):
            score = 0.9 if index % 2 == 0 else 0.1
            _run(db, metric, org_id, {"score": score, "reason": f"run {index}"})
            if index == 0:
                _accepted(client, metric.id, case_id)
            else:
                _rejected(client, metric.id, case_id, f"wrong #{index}")

    def test_the_cap_evicts_the_accept(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        numeric_metric: models.Metric,
    ):
        case = _create_case(authenticated_client, numeric_metric.id)

        self._push_reviews(
            authenticated_client,
            test_db,
            numeric_metric,
            test_org_id,
            case["id"],
            REVIEW_HISTORY_LIMIT + 1,
        )

        stored = _stored_reviews(test_db, case["id"])
        assert len(stored) == REVIEW_HISTORY_LIMIT
        assert all(review["decision"] == "rejected" for review in stored)
        assert [review["comment"] for review in stored] == [
            f"wrong #{index}" for index in range(1, REVIEW_HISTORY_LIMIT + 1)
        ]

    def test_the_cap_gives_way_rather_than_dropping_a_comment(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        numeric_metric: models.Metric,
    ):
        """A cap that silently dropped comments would destroy what the feature
        produces, so with no accept left to evict the history grows instead."""
        case = _create_case(authenticated_client, numeric_metric.id)

        self._push_reviews(
            authenticated_client,
            test_db,
            numeric_metric,
            test_org_id,
            case["id"],
            REVIEW_HISTORY_LIMIT + 2,
        )

        stored = _stored_reviews(test_db, case["id"])
        assert len(stored) == REVIEW_HISTORY_LIMIT + 1
        assert [review["comment"] for review in stored] == [
            f"wrong #{index}" for index in range(1, REVIEW_HISTORY_LIMIT + 2)
        ]


@pytest.mark.integration
@pytest.mark.routes
class TestReviewsAreInvisibleToTheMetric:
    """A scorecard has to reflect the metric's judgement, not its ability to
    read a reviewer's hint."""

    def test_reviewing_does_not_change_what_the_case_shows_the_metric(
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
        assert REVIEW_COMMENT not in prompt.content
        # The column the normal evaluation path would hand the metric as a
        # reference answer stays empty for a tuning case.
        assert prompt.expected_response is None
