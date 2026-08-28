"""Integration tests for improving a metric from the rejections its reviewers wrote.

Tests one endpoint:
- POST /metrics/{metric_id}/tuning/improve

This is the reader the comments were collected for. What it must get right is
mostly about restraint: it proposes and never writes, only rejections that still
stand reach the model, and the two fields a rewrite is not allowed to move come
back as the metric has them. See domain.local/adr/0006.

The generation model is stubbed throughout, so these are deterministic and free
of LLM calls. The metric invocation is stubbed too -- a rejection needs a verdict
to be a rejection of, so most of these run the metric first.

The test that matters most is ``test_it_writes_nothing``. Every alternative
ADR-0006 rejected fails it: rewriting in place, or applying by asking the model a
second time, both leave the metric changed by a request that was only meant to
propose.

Run with: python -m pytest tests/backend/routes/test_metric_tuning_improve.py -v
"""

import uuid
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud import metric_tuning as crud_metric_tuning
from rhesis.backend.app.schemas.metric import MetricScope
from rhesis.backend.app.schemas.metric_tuning_metadata import (
    MetricTuningReview,
    ReviewDecision,
    parse_metric_tuning_case_metadata,
)
from rhesis.backend.app.services import metric_tuning as service
from rhesis.backend.app.services.metric_tuning.improve import (
    TEXT_FIELD_LIMIT,
    TRUNCATION_MARKER,
)
from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup

IMPROVE = "rhesis.backend.app.services.metric_tuning.improve"

CASE_INPUT = "How are you?"
CASE_OUTPUT = "I am fine you fucking basterd"
CASE_REFERENCE_ANSWER = "I am fine, thanks for asking."
REVIEW_COMMENT = "the metric called this harmless, but it is plainly toxic"

# What the metric said, and what it said about saying it.
VERDICT_REASON = "No slur or threat is present in the answer."

NEW_PROMPT = "Fail any answer containing an insult, however mild the rest of it is."

BASE_IMPROVEMENT = {
    "name": "Toxicity",
    "description": "Whether the answer insults the person it is answering.",
    "evaluation_prompt": NEW_PROMPT,
    "evaluation_steps": "Step 1:\nRead the answer.\n---\nStep 2:\nScore it.",
    "reasoning": "Quote the phrase judged insulting and tie it to the clause it breaks.",
    "explanation": "A fail means the answer insults the user. Rewrite it before shipping.",
    "score_type": "binary",
    "min_score": None,
    "max_score": None,
    "threshold": None,
    "threshold_operator": None,
    "categories": None,
    "passing_categories": None,
}


def _make_model(db: Session, organization_id, user_id) -> models.Model:
    """A judging model for the metric, so a run is not refused before it starts.

    Deliberately present in every metric here: the improvement must use the
    *generation* model regardless, and a metric with a judge of its own is what
    makes that assertion mean something.
    """
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
        evaluation_steps="Step 1:\nRead the answer.",
        reasoning="Say which phrase decided it.",
        explanation="A fail means the answer is toxic.",
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
        test_db, f"Toxicity Improve {uuid.uuid4().hex[:6]}", test_org_id, authenticated_user_id
    )


@pytest.fixture
def numeric_metric(test_db: Session, test_org_id, authenticated_user_id) -> models.Metric:
    """A numeric metric — its threshold is what decides whether a review stands."""
    return _make_metric(
        test_db,
        f"Numeric Improve {uuid.uuid4().hex[:6]}",
        test_org_id,
        authenticated_user_id,
        score_type="numeric",
        min_score=0.0,
        max_score=1.0,
        threshold=0.5,
        threshold_operator=">=",
    )


@pytest.fixture
def categorical_metric(test_db: Session, test_org_id, authenticated_user_id) -> models.Metric:
    return _make_metric(
        test_db,
        f"Categorical Improve {uuid.uuid4().hex[:6]}",
        test_org_id,
        authenticated_user_id,
        score_type="categorical",
        categories=["helpful", "harmful"],
        passing_categories=["helpful"],
    )


@pytest.fixture
def framework_metric(test_db: Session, test_org_id, authenticated_user_id) -> models.Metric:
    """A framework-provided metric — its prompt is not the org's to rewrite."""
    return _make_metric(
        test_db,
        f"Framework Improve {uuid.uuid4().hex[:6]}",
        test_org_id,
        authenticated_user_id,
        backend_type="deepeval",
    )


@pytest.fixture
def unknown_score_type_metric(test_db: Session, test_org_id, authenticated_user_id):
    """A metric whose stored score type no schema of ours knows.

    The column is a plain string, so this is reachable, and it is the one way the
    fields we would apply can fail validation: the score type is put back exactly
    as stored, and ``MetricUpdate`` refuses it.
    """
    return _make_metric(
        test_db,
        f"Rubric Improve {uuid.uuid4().hex[:6]}",
        test_org_id,
        authenticated_user_id,
        score_type="rubric",
    )


class _GenerationModel:
    """The stubbed generation model, plus what it was asked."""

    def __init__(self, picked: MagicMock, model: MagicMock):
        self.picked = picked
        self.model = model
        self.answers()

    def answers(self, **overrides) -> None:
        """Make the model answer with the base improvement, patched by overrides."""
        self.model.generate.side_effect = None
        self.model.generate.return_value = {**BASE_IMPROVEMENT, **overrides}

    def answers_with(self, answer) -> None:
        """Make the model answer with something else entirely."""
        self.model.generate.side_effect = None
        self.model.generate.return_value = answer

    def raises(self, error: Exception) -> None:
        self.model.generate.side_effect = error

    @property
    def asked(self) -> bool:
        return self.model.generate.called

    @property
    def prompt(self) -> str:
        """The prompt the model was actually given."""
        assert self.model.generate.call_args is not None, "the model was never asked"
        return self.model.generate.call_args.args[0]


@pytest.fixture
def generation_model():
    """Stub the user's generation model.

    A test can assert the model came from the user's *generation* setting — the
    metric's own judge is a different model, and every metric here has one.
    """
    model = MagicMock()
    with patch(f"{IMPROVE}.resolve_model", return_value=model) as picked:
        yield _GenerationModel(picked, model)


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
    """A stubbed MetricEvaluator whose evaluate() yields the given results.

    ``by_input`` keys the results on the case's input rather than on call order,
    which is the only way to land a particular verdict on a particular case:
    every case created inside one test shares a ``created_at``, so the run walks
    them in id order rather than insertion order.
    """
    calls = list(results)
    evaluator = MagicMock()

    def _evaluate(**kwargs):
        if by_input is not None:
            outcome = by_input[kwargs["input_text"]]
        else:
            outcome = calls.pop(0) if calls else {"score": 0.0, "reason": VERDICT_REASON}
        if isinstance(outcome, Exception):
            raise outcome
        return {"Metric": outcome}

    evaluator.evaluate.side_effect = _evaluate
    return MagicMock(return_value=evaluator)


def _run(db: Session, metric: models.Metric, org_id, *results, by_input=None) -> None:
    """Execute a run with the metric invocation stubbed.

    Expires the session first: the cases were written by requests on their own
    sessions, and a background worker always starts from a fresh one.
    """
    db.expire_all()
    factory = _evaluator_returning(*results, by_input=by_input)
    with patch("rhesis.backend.metrics.evaluator.MetricEvaluator", factory):
        service.execute_tuning_run(db, metric, org_id, None)


def _review(client: TestClient, metric_id, case_id, decision: str, comment=None) -> dict:
    body = {"decision": decision}
    if comment is not None:
        body["comment"] = comment
    response = client.post(f"/metrics/{metric_id}/tuning/cases/{case_id}/review", json=body)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


def _reject(client: TestClient, metric_id, case_id, comment: str = REVIEW_COMMENT) -> dict:
    return _review(client, metric_id, case_id, "rejected", comment)


def _accept(client: TestClient, metric_id, case_id) -> dict:
    return _review(client, metric_id, case_id, "accepted")


def _write_review(
    db: Session,
    case_id,
    *,
    decision: ReviewDecision,
    verdict: str,
    score_type: str,
    comment: Optional[str] = None,
    reviewer_id: Optional[str] = None,
) -> None:
    """Append a review to a case's history directly.

    The review endpoint always stamps the caller as the reviewer, so a review
    written by somebody else has to be written here. Everything else about the
    row is exactly what the endpoint would have stored.
    """
    db.expire_all()
    db_test = db.query(models.Test).filter(models.Test.id == uuid.UUID(str(case_id))).first()
    metadata = parse_metric_tuning_case_metadata(db_test.test_metadata)
    reviews = list(metadata.reviews)
    reviews.append(
        MetricTuningReview(
            decision=decision,
            comment=comment,
            verdict=verdict,
            score_type=score_type,
            reviewer_id=reviewer_id,
            reviewed_at="2026-08-20T10:00:00+00:00",
        )
    )
    crud_metric_tuning.set_case_reviews(db, db_test, reviews)
    db.commit()


def _improve(client: TestClient, metric_id):
    return client.post(f"/metrics/{metric_id}/tuning/improve")


def _improved(client: TestClient, metric_id) -> dict:
    response = _improve(client, metric_id)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


def _stored_reviews(db: Session, case_id) -> List[dict]:
    db.expire_all()
    db_test = db.query(models.Test).filter(models.Test.id == uuid.UUID(str(case_id))).first()
    return (db_test.test_metadata or {}).get("reviews", [])


def _rejected_case(client: TestClient, db: Session, metric: models.Metric, org_id, **case) -> dict:
    """One case, run over, and rejected with a comment. The usual starting point."""
    created = _create_case(client, metric.id, **case)
    _run(db, metric, org_id)
    return _reject(client, metric.id, created["id"])


@pytest.mark.integration
class TestRefusals:
    """When there is nothing to read, or nothing that may be rewritten."""

    def test_a_metric_with_no_cases_is_refused(
        self, authenticated_client: TestClient, tuning_metric, generation_model
    ):
        response = _improve(authenticated_client, tuning_metric.id)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "reject" in response.json()["detail"].lower()

    def test_a_metric_whose_cases_are_all_accepted_is_refused(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        created = _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id)
        _accept(authenticated_client, tuning_metric.id, created["id"])

        response = _improve(authenticated_client, tuning_metric.id)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_an_unreviewed_case_is_not_something_to_learn_from(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id)

        assert (
            _improve(authenticated_client, tuning_metric.id).status_code
            == status.HTTP_400_BAD_REQUEST
        )

    def test_nothing_is_asked_of_the_model_when_there_is_nothing_to_read(
        self, authenticated_client: TestClient, tuning_metric, generation_model
    ):
        """A refusal must not cost an LLM call."""
        _improve(authenticated_client, tuning_metric.id)

        assert generation_model.asked is False

    def test_a_framework_metric_is_refused(
        self, authenticated_client: TestClient, framework_metric, generation_model
    ):
        response = _improve(authenticated_client, framework_metric.id)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "custom" in response.json()["detail"].lower()

    def test_an_unknown_metric_404s(self, authenticated_client: TestClient, generation_model):
        response = _improve(authenticated_client, uuid.uuid4())

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
class TestTheImprovement:
    """The shape of what comes back, and what it leaves behind."""

    def test_it_returns_the_proposed_fields_and_the_rejection_count(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        _rejected_case(authenticated_client, test_db, tuning_metric, test_org_id)

        body = _improved(authenticated_client, tuning_metric.id)

        assert body["improvement"]["evaluation_prompt"] == NEW_PROMPT
        assert body["rejections_used"] == 1

    def test_it_counts_every_rejection_it_used(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        first = _create_case(authenticated_client, tuning_metric.id, input="One")
        second = _create_case(authenticated_client, tuning_metric.id, input="Two")
        _run(test_db, tuning_metric, test_org_id)
        _reject(authenticated_client, tuning_metric.id, first["id"])
        _reject(authenticated_client, tuning_metric.id, second["id"])

        assert _improved(authenticated_client, tuning_metric.id)["rejections_used"] == 2

    def test_it_names_the_fields_that_changed(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        _rejected_case(authenticated_client, test_db, tuning_metric, test_org_id)
        generation_model.answers(name=tuning_metric.name)

        changed = _improved(authenticated_client, tuning_metric.id)["changed"]

        assert "evaluation_prompt" in changed
        # Returned unchanged, so the dialog says so rather than showing it.
        assert "name" not in changed

    def test_a_rewrite_that_changed_nothing_names_nothing(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        _rejected_case(authenticated_client, test_db, tuning_metric, test_org_id)
        generation_model.answers(
            name=tuning_metric.name,
            description=tuning_metric.description,
            evaluation_prompt=tuning_metric.evaluation_prompt,
            evaluation_steps=tuning_metric.evaluation_steps,
            reasoning=tuning_metric.reasoning,
            explanation=tuning_metric.explanation,
            # A binary metric carries a threshold operator it never uses -- the
            # column defaults to one. The template tells the model to hand those
            # back untouched, so a difference here would be noise.
            threshold_operator=tuning_metric.threshold_operator,
        )

        assert _improved(authenticated_client, tuning_metric.id)["changed"] == []

    def test_it_writes_nothing(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        """Producing an improvement never saves one. This is the whole of ADR-0006."""
        before = tuning_metric.evaluation_prompt
        _rejected_case(authenticated_client, test_db, tuning_metric, test_org_id)

        _improved(authenticated_client, tuning_metric.id)

        test_db.expire_all()
        after = test_db.query(models.Metric).filter(models.Metric.id == tuning_metric.id).first()
        assert after.evaluation_prompt == before

    def test_it_leaves_the_reviews_alone(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        """Reading the comments is not judging them again."""
        case = _rejected_case(authenticated_client, test_db, tuning_metric, test_org_id)
        before = _stored_reviews(test_db, case["id"])

        _improved(authenticated_client, tuning_metric.id)

        assert _stored_reviews(test_db, case["id"]) == before

    def test_the_score_type_comes_back_as_the_metric_has_it(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        categorical_metric,
        test_org_id,
        generation_model,
    ):
        """Changing it would invalidate every review the metric has."""
        _create_case(authenticated_client, categorical_metric.id)
        _run(test_db, categorical_metric, test_org_id, {"score": "helpful", "reason": "polite"})
        cases = authenticated_client.get(f"/metrics/{categorical_metric.id}/tuning/cases").json()
        _reject(authenticated_client, categorical_metric.id, cases[0]["id"])
        generation_model.answers(score_type="numeric", categories=["good", "bad"])

        improvement = _improved(authenticated_client, categorical_metric.id)["improvement"]

        assert improvement["score_type"] == "categorical"
        assert improvement["categories"] == ["helpful", "harmful"]

    def test_a_field_the_metric_has_is_never_proposed_empty(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        numeric_metric,
        test_org_id,
        generation_model,
    ):
        """An improvement can change a field but cannot clear one.

        A metric update drops a null instead of writing it, so a blank proposal
        would show as "—" in the dialog, apply successfully, and leave the old
        value in place -- exactly the gap between approved and saved that
        ADR-0006 exists to close.
        """
        _create_case(authenticated_client, numeric_metric.id)
        _run(test_db, numeric_metric, test_org_id, {"score": 0.7, "reason": VERDICT_REASON})
        cases = authenticated_client.get(f"/metrics/{numeric_metric.id}/tuning/cases").json()
        _reject(authenticated_client, numeric_metric.id, cases[0]["id"])
        generation_model.answers(score_type="numeric", threshold=None, threshold_operator=None)

        body = _improved(authenticated_client, numeric_metric.id)

        assert body["improvement"]["threshold"] == 0.5
        assert body["improvement"]["threshold_operator"] == ">="
        assert "threshold" not in body["changed"]

    def test_a_field_the_metric_lacks_stays_empty(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        """Nothing is invented to fill a field the metric never had."""
        _rejected_case(authenticated_client, test_db, tuning_metric, test_org_id)

        assert _improved(authenticated_client, tuning_metric.id)["improvement"]["threshold"] is None

    def test_the_threshold_may_change(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        numeric_metric,
        test_org_id,
        generation_model,
    ):
        """ "This should have failed" is very often a threshold statement."""
        _create_case(authenticated_client, numeric_metric.id)
        _run(test_db, numeric_metric, test_org_id, {"score": 0.7, "reason": VERDICT_REASON})
        cases = authenticated_client.get(f"/metrics/{numeric_metric.id}/tuning/cases").json()
        _reject(authenticated_client, numeric_metric.id, cases[0]["id"])
        generation_model.answers(
            score_type="numeric",
            min_score=0.0,
            max_score=1.0,
            threshold=0.9,
            threshold_operator=">=",
        )

        body = _improved(authenticated_client, numeric_metric.id)

        assert body["improvement"]["threshold"] == 0.9
        assert "threshold" in body["changed"]


@pytest.mark.integration
class TestWhatTheModelIsShown:
    """Which rejections reach the prompt, and what each one carries."""

    def test_a_rejection_carries_the_case_the_verdict_and_the_comment(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        _rejected_case(authenticated_client, test_db, tuning_metric, test_org_id)

        _improved(authenticated_client, tuning_metric.id)
        prompt = generation_model.prompt

        assert CASE_INPUT in prompt
        assert CASE_OUTPUT in prompt
        assert CASE_REFERENCE_ANSWER in prompt
        assert VERDICT_REASON in prompt
        assert REVIEW_COMMENT in prompt

    def test_the_verdict_and_the_reasoning_come_from_the_same_run(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        numeric_metric,
        test_org_id,
        generation_model,
    ):
        """A review outlives drift that did not cross the threshold, so the
        verdict it recorded can be a run behind the reasoning beside it.

        Showing the model a score next to an explanation of a different score is
        worse than showing it either alone.
        """
        case = _create_case(authenticated_client, numeric_metric.id)
        _run(test_db, numeric_metric, test_org_id, {"score": 0.79, "reason": "mostly relevant"})
        _reject(authenticated_client, numeric_metric.id, case["id"])
        # Same side of the 0.5 threshold, so the rejection still stands.
        _run(test_db, numeric_metric, test_org_id, {"score": 0.81, "reason": "still relevant"})

        _improved(authenticated_client, numeric_metric.id)
        prompt = generation_model.prompt

        assert "0.81" in prompt
        assert "still relevant" in prompt
        assert "0.79" not in prompt
        assert "mostly relevant" not in prompt

    def test_an_accepted_case_is_not_sent(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        rejected = _create_case(authenticated_client, tuning_metric.id, input="The rejected one")
        accepted = _create_case(authenticated_client, tuning_metric.id, input="The accepted one")
        _run(test_db, tuning_metric, test_org_id)
        _reject(authenticated_client, tuning_metric.id, rejected["id"])
        _accept(authenticated_client, tuning_metric.id, accepted["id"])

        body = _improved(authenticated_client, tuning_metric.id)

        assert body["rejections_used"] == 1
        assert "The rejected one" in generation_model.prompt
        assert "The accepted one" not in generation_model.prompt

    def test_a_rejection_a_material_change_invalidated_is_not_sent(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        numeric_metric,
        test_org_id,
        generation_model,
    ):
        """It objects to a verdict the metric no longer gives."""
        standing = _create_case(authenticated_client, numeric_metric.id, input="Still wrong")
        invalidated = _create_case(authenticated_client, numeric_metric.id, input="Fixed since")
        _run(
            test_db,
            numeric_metric,
            test_org_id,
            by_input={
                "Still wrong": {"score": 0.8, "reason": "ok"},
                "Fixed since": {"score": 0.8, "reason": "ok"},
            },
        )
        _reject(authenticated_client, numeric_metric.id, standing["id"], "still too generous")
        _reject(
            authenticated_client, numeric_metric.id, invalidated["id"], "should not have passed"
        )
        # A second run drops one verdict below the threshold, which is what makes
        # that review stop describing the metric.
        _run(
            test_db,
            numeric_metric,
            test_org_id,
            by_input={
                "Still wrong": {"score": 0.8, "reason": "ok"},
                "Fixed since": {"score": 0.2, "reason": "ok"},
            },
        )

        body = _improved(authenticated_client, numeric_metric.id)

        assert body["rejections_used"] == 1
        assert "still too generous" in generation_model.prompt
        assert "should not have passed" not in generation_model.prompt

    def test_only_the_latest_review_of_a_case_is_sent(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        """The ten-deep history is storage, not the judgement in force."""
        case = _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id)
        _reject(authenticated_client, tuning_metric.id, case["id"], "an earlier objection")
        _reject(authenticated_client, tuning_metric.id, case["id"], "what I actually think")

        body = _improved(authenticated_client, tuning_metric.id)

        assert body["rejections_used"] == 1
        assert "what I actually think" in generation_model.prompt
        assert "an earlier objection" not in generation_model.prompt

    def test_a_case_rejected_then_accepted_is_not_sent(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        case = _rejected_case(authenticated_client, test_db, tuning_metric, test_org_id)
        _accept(authenticated_client, tuning_metric.id, case["id"])

        assert (
            _improve(authenticated_client, tuning_metric.id).status_code
            == status.HTTP_400_BAD_REQUEST
        )

    def test_another_reviewers_rejection_is_sent_too(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        """A metric is tuned by everyone who reviewed it, not by whoever pressed
        the button."""
        case = _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id)
        _write_review(
            test_db,
            case["id"],
            decision=ReviewDecision.REJECTED,
            verdict="fail",
            score_type="binary",
            comment="somebody else noticed this",
            reviewer_id=str(uuid.uuid4()),
        )

        body = _improved(authenticated_client, tuning_metric.id)

        assert body["rejections_used"] == 1
        assert "somebody else noticed this" in generation_model.prompt

    def test_every_rejection_is_sent_however_many_there_are(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        """No cap and no silent truncation: a dropped comment is a lost finding."""
        comments = [f"objection number {index}" for index in range(12)]
        created = [
            _create_case(authenticated_client, tuning_metric.id, input=f"Case {index}")
            for index in range(len(comments))
        ]
        _run(test_db, tuning_metric, test_org_id)
        for case, comment in zip(created, comments):
            _reject(authenticated_client, tuning_metric.id, case["id"], comment)

        body = _improved(authenticated_client, tuning_metric.id)

        assert body["rejections_used"] == len(comments)
        for comment in comments:
            assert comment in generation_model.prompt

    def test_a_long_field_is_cut_and_says_so(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        """Capped generously, and marked — never trimmed in silence."""
        long_output = "x" * (TEXT_FIELD_LIMIT + 500)
        _rejected_case(
            authenticated_client, test_db, tuning_metric, test_org_id, output=long_output
        )

        _improved(authenticated_client, tuning_metric.id)

        assert long_output not in generation_model.prompt
        assert TRUNCATION_MARKER in generation_model.prompt

    def test_the_metrics_current_fields_are_shown_beside_the_rejections(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        """A rewrite of a prompt has to be shown the prompt."""
        _rejected_case(authenticated_client, test_db, tuning_metric, test_org_id)

        _improved(authenticated_client, tuning_metric.id)

        assert tuning_metric.evaluation_prompt in generation_model.prompt


@pytest.mark.integration
class TestTheModelItUses:
    def test_it_uses_the_users_generation_model(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        """Not the metric's judge, which every metric here also has.

        Writing an evaluation prompt is a generation task, so the user's
        generation choice is the one that applies.
        """
        _rejected_case(authenticated_client, test_db, tuning_metric, test_org_id)

        _improved(authenticated_client, tuning_metric.id)

        generation_model.picked.assert_called_once()
        assert generation_model.picked.call_args.args[2] == "generation"


@pytest.mark.integration
class TestFailures:
    def test_a_generation_model_failure_is_a_400(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        _rejected_case(authenticated_client, test_db, tuning_metric, test_org_id)
        generation_model.raises(RuntimeError("the provider returned 401"))

        response = _improve(authenticated_client, tuning_metric.id)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == (
            "Failed to improve metric: the generation model could not be used. "
            "Check the model configured for your organization."
        )

    def test_a_failure_does_not_leak_the_providers_own_words(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        _rejected_case(authenticated_client, test_db, tuning_metric, test_org_id)
        generation_model.raises(RuntimeError("sk-secret-key rejected"))

        assert "sk-secret-key" not in _improve(authenticated_client, tuning_metric.id).text

    def test_an_answer_in_the_wrong_shape_is_a_400(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        """Some providers report their own failure as an answer rather than raising."""
        _rejected_case(authenticated_client, test_db, tuning_metric, test_org_id)
        generation_model.answers_with({"error": "An error occurred while processing the request."})

        assert (
            _improve(authenticated_client, tuning_metric.id).status_code
            == status.HTTP_400_BAD_REQUEST
        )

    def test_an_answer_missing_a_required_field_is_a_400(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric,
        test_org_id,
        generation_model,
    ):
        _rejected_case(authenticated_client, test_db, tuning_metric, test_org_id)
        answer = dict(BASE_IMPROVEMENT)
        del answer["reasoning"]
        generation_model.answers_with(answer)

        assert (
            _improve(authenticated_client, tuning_metric.id).status_code
            == status.HTTP_400_BAD_REQUEST
        )

    def test_fields_that_could_not_be_applied_are_a_500(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        unknown_score_type_metric,
        test_org_id,
        generation_model,
    ):
        """Our schema, not the caller's request — so it is ours to see in a log."""
        _rejected_case(authenticated_client, test_db, unknown_score_type_metric, test_org_id)

        response = _improve(authenticated_client, unknown_score_type_metric.id)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
