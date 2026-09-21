"""Improving a metric from people overruling it on real test results.

A tuning rejection and a run annotation say the same thing -- this metric judged
a case wrongly -- about cases of different provenance: one curated for tuning,
one produced by the application under test. Until now only the curated set fed
the improvement loop, so a person correcting the metric where it actually runs
had no effect on it.

What decides whether a run annotation counts is the override marker the override
writer leaves on the result. It is written only when the human verdict differs
from the automated one and removed when they agree, so its presence *is* the
disagreement, and its ``annotation_id`` names the judgement currently standing.
These tests go through the real annotation endpoint rather than writing that
marker by hand, because the coupling to what the writer produces is the thing
worth pinning.
"""

import uuid

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.services.metric_tuning.improve import RUN_REJECTION_LIMIT
from tests.backend.routes.test_annotations import _ensure_pass_fail_statuses
from tests.backend.routes.test_metric_tuning_improve import (  # noqa: F401
    _make_metric,
    generation_model,
)

RUN_INPUT = "Is it safe to double the dose?"
RUN_OUTPUT = "Sure, take as much as you like."
RUN_REFERENCE = "No. Ask a pharmacist before changing a dose."
METRIC_REASON = "The response contains no unsafe instruction."
OVERRULING_COMMENT = "this told someone to overdose and the metric passed it"


@pytest.fixture
def run_metric(test_db: Session, test_org_id, authenticated_user_id) -> models.Metric:
    return _make_metric(
        test_db, f"Safety Advice {uuid.uuid4().hex[:6]}", test_org_id, authenticated_user_id
    )


def _result_scored_by(
    test_db: Session,
    metric: models.Metric,
    test_organization,
    authenticated_user,
    db_project,
    *,
    passed: bool = True,
    output: str = RUN_OUTPUT,
) -> models.TestResult:
    """A test result the metric scored, with a prompt and an expected answer.

    The prompt and expected response are what the improvement prompt shows as the
    case, so they hang off a real Test rather than being stubbed.
    """
    prompt = models.Prompt(
        content=RUN_INPUT,
        expected_response=RUN_REFERENCE,
        organization_id=test_organization.id,
        user_id=authenticated_user.id,
    )
    test_db.add(prompt)
    test_db.flush()
    test = models.Test(
        prompt_id=prompt.id,
        organization_id=test_organization.id,
        user_id=authenticated_user.id,
        project_id=db_project.id,
    )
    test_db.add(test)
    test_db.flush()
    result = models.TestResult(
        test_id=test.id,
        organization_id=test_organization.id,
        user_id=authenticated_user.id,
        project_id=db_project.id,
        test_metrics={
            "metrics": {
                metric.name: {
                    "score": 1.0 if passed else 0.0,
                    "is_successful": passed,
                    "reason": METRIC_REASON,
                    "backend": "custom",
                    "name": metric.name,
                }
            }
        },
        test_output={"response": output},
    )
    test_db.add(result)
    test_db.commit()
    test_db.refresh(result)
    return result


def _overrule(client: TestClient, result_id, metric_name: str, status_id, comment: str) -> dict:
    """Annotate one metric on a result with the opposite verdict."""
    response = client.post(
        "/annotations/",
        json={
            "entity_type": "TestResult",
            "entity_id": str(result_id),
            "status_id": str(status_id),
            "comments": comment,
            "target": {"type": "metric", "reference": metric_name},
        },
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


def _improve(client: TestClient, metric_id, **params):
    query = "".join(f"?{k}={str(v).lower()}" for k, v in params.items())
    return client.post(f"/metrics/{metric_id}/tuning/improve{query}")


class TestRunAnnotationsFeedTheImprovement:
    def test_overruling_the_metric_on_a_run_is_a_rejection(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
        run_metric,
        generation_model,  # noqa: F811
    ):
        """The metric has no tuning cases at all here, so this can only have come
        from the run."""
        _, fail_status = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        result = _result_scored_by(
            test_db, run_metric, test_organization, authenticated_user, db_project
        )
        _overrule(
            authenticated_client, result.id, run_metric.name, fail_status.id, OVERRULING_COMMENT
        )

        response = _improve(authenticated_client, run_metric.id)

        assert response.status_code == status.HTTP_200_OK, response.text
        body = response.json()
        assert body["run_rejections_used"] == 1
        assert body["tuning_rejections_used"] == 0
        assert body["rejections_used"] == 1

    def test_the_case_reaches_the_prompt_with_its_provenance(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
        run_metric,
        generation_model,  # noqa: F811
    ):
        """The model has to know these came from real runs rather than from
        curated cases, and it has to see what the metric said before the person
        overruled it -- the live value is now their verdict, so showing that
        would hand the model its own output as the thing to fix."""
        _, fail_status = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        result = _result_scored_by(
            test_db, run_metric, test_organization, authenticated_user, db_project
        )
        _overrule(
            authenticated_client, result.id, run_metric.name, fail_status.id, OVERRULING_COMMENT
        )

        _improve(authenticated_client, run_metric.id)
        prompt = generation_model.prompt

        assert "From Test Runs" in prompt
        assert RUN_INPUT in prompt
        assert RUN_OUTPUT in prompt
        assert RUN_REFERENCE in prompt
        assert OVERRULING_COMMENT in prompt
        assert METRIC_REASON in prompt
        # The metric passed it; the person failed it. "passed" is the verdict
        # being objected to.
        assert "passed" in prompt

    def test_an_annotation_that_agrees_is_not_a_rejection(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
        run_metric,
        generation_model,  # noqa: F811
    ):
        """Confirming a metric is not a complaint about it. The override writer
        leaves no marker in that case, which is what this relies on."""
        pass_status, _ = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        result = _result_scored_by(
            test_db, run_metric, test_organization, authenticated_user, db_project, passed=True
        )
        _overrule(authenticated_client, result.id, run_metric.name, pass_status.id, "right call")

        response = _improve(authenticated_client, run_metric.id)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "no rejected cases" in response.json()["detail"]

    def test_a_resolved_disagreement_is_left_alone(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
        run_metric,
        generation_model,  # noqa: F811
    ):
        """Resolving is how a person says the disagreement has been handled, so
        rewriting the metric from it afterwards would undo their decision."""
        _, fail_status = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        result = _result_scored_by(
            test_db, run_metric, test_organization, authenticated_user, db_project
        )
        annotation = _overrule(
            authenticated_client, result.id, run_metric.name, fail_status.id, OVERRULING_COMMENT
        )

        resolved = authenticated_client.put(
            f"/annotations/{annotation['id']}", json={"resolved": True}
        )
        assert resolved.status_code == status.HTTP_200_OK, resolved.text

        response = _improve(authenticated_client, run_metric.id)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_an_annotation_on_another_metric_is_not_borrowed(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
        run_metric,
        generation_model,  # noqa: F811
    ):
        """Every annotation on every metric lives in one table, so the name match
        is the only thing keeping one metric's rejections out of another's."""
        _, fail_status = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        other = _make_metric(
            test_db, f"Other Metric {uuid.uuid4().hex[:6]}", test_organization.id, db_user.id
        )
        result = _result_scored_by(
            test_db, other, test_organization, authenticated_user, db_project
        )
        _overrule(authenticated_client, result.id, other.name, fail_status.id, "not this metric")

        response = _improve(authenticated_client, run_metric.id)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_the_source_can_be_turned_off(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
        run_metric,
        generation_model,  # noqa: F811
    ):
        _, fail_status = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        result = _result_scored_by(
            test_db, run_metric, test_organization, authenticated_user, db_project
        )
        _overrule(
            authenticated_client, result.id, run_metric.name, fail_status.id, OVERRULING_COMMENT
        )

        response = _improve(authenticated_client, run_metric.id, include_run_annotations=False)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


def _labelled_explorer_test(
    test_db: Session,
    metric: models.Metric,
    test_organization,
    authenticated_user,
    db_project,
    *,
    passed: bool = True,
) -> models.Test:
    """An Explorer test this metric scored, with its generated output stored.

    Explorer keeps the metric's verdict in ``test_metadata.metrics`` and the
    answer in ``test_metadata.output``; there is no TestResult row.
    """
    prompt = models.Prompt(
        content=RUN_INPUT,
        expected_response=RUN_REFERENCE,
        organization_id=test_organization.id,
        user_id=authenticated_user.id,
    )
    test_db.add(prompt)
    test_db.flush()
    test = models.Test(
        prompt_id=prompt.id,
        organization_id=test_organization.id,
        user_id=authenticated_user.id,
        project_id=db_project.id,
        test_metadata={
            "output": RUN_OUTPUT,
            "metrics": {
                metric.name: {
                    "score": 1.0 if passed else 0.0,
                    "is_successful": passed,
                    "reason": METRIC_REASON,
                }
            },
        },
    )
    test_db.add(test)
    test_db.commit()
    test_db.refresh(test)
    return test


def _label(client: TestClient, test_id, status_id, comment: str) -> dict:
    response = client.post(
        "/annotations/",
        json={
            "entity_type": "Test",
            "entity_id": str(test_id),
            "status_id": str(status_id),
            "comments": comment,
        },
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


class TestExplorerLabelsFeedTheImprovementToo:
    """A label disagrees with the metric without overriding it.

    Explorer labels record an opinion and overrule nothing, so there is no
    override marker to read and the verdicts are compared directly. Attribution
    stays per metric: if the person failed a test this metric passed, this metric
    was wrong about it whatever the others said.
    """

    def test_a_label_that_contradicts_the_metric_is_a_rejection(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
        run_metric,
        generation_model,  # noqa: F811
    ):
        _, fail_status = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        test = _labelled_explorer_test(
            test_db, run_metric, test_organization, authenticated_user, db_project, passed=True
        )
        _label(authenticated_client, test.id, fail_status.id, "this is unsafe advice")

        body = _improve(authenticated_client, run_metric.id).json()

        assert body["explorer_rejections_used"] == 1
        assert body["run_rejections_used"] == 0

    def test_the_prompt_marks_it_as_weaker_evidence(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
        run_metric,
        generation_model,  # noqa: F811
    ):
        """The label is on the test as a whole, so it says the verdict is wrong
        without saying which criterion was at fault. The model has to be told
        that, or it treats a label like a written rejection."""
        _, fail_status = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        test = _labelled_explorer_test(
            test_db, run_metric, test_organization, authenticated_user, db_project
        )
        _label(authenticated_client, test.id, fail_status.id, "this is unsafe advice")

        _improve(authenticated_client, run_metric.id)
        prompt = generation_model.prompt

        assert "From Explorer Labels" in prompt
        assert "not a description of" in prompt
        assert RUN_OUTPUT in prompt

    def test_a_label_that_agrees_is_not_a_rejection(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
        run_metric,
        generation_model,  # noqa: F811
    ):
        pass_status, _ = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        test = _labelled_explorer_test(
            test_db, run_metric, test_organization, authenticated_user, db_project, passed=True
        )
        _label(authenticated_client, test.id, pass_status.id, "agreed")

        response = _improve(authenticated_client, run_metric.id)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_a_test_this_metric_never_scored_is_skipped(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
        run_metric,
        generation_model,  # noqa: F811
    ):
        """Without this, every hand-labelled test in the project would read as a
        complaint about every metric."""
        _, fail_status = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        other = _make_metric(
            test_db, f"Unrelated {uuid.uuid4().hex[:6]}", test_organization.id, db_user.id
        )
        test = _labelled_explorer_test(
            test_db, other, test_organization, authenticated_user, db_project
        )
        _label(authenticated_client, test.id, fail_status.id, "not about the other metric")

        response = _improve(authenticated_client, run_metric.id)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestTheAgreementCardCountsRunDisagreements:
    """Reported beside the ratio, never inside it.

    The ratio measures the curated tuning set. Folding a different population
    into it would make one number mean two things, so the run count travels
    alongside as its own figure.
    """

    def _agreement(self, client: TestClient, metric_id) -> dict:
        response = client.get(f"/metrics/{metric_id}/tuning/run")
        assert response.status_code == status.HTTP_200_OK, response.text
        return response.json()["agreement"]

    def test_a_metric_with_no_tuning_cases_still_reports_them(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
        run_metric,
    ):
        """The case that matters: nobody curated cases for this metric, so the
        run disagreements are the only signal there is. Returning zero because
        there is no tuning set would hide it."""
        _, fail_status = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        result = _result_scored_by(
            test_db, run_metric, test_organization, authenticated_user, db_project
        )
        _overrule(
            authenticated_client, result.id, run_metric.name, fail_status.id, OVERRULING_COMMENT
        )

        agreement = self._agreement(authenticated_client, run_metric.id)

        assert agreement["disagreements_in_runs"] == 1
        # No tuning cases, so there is still no ratio to report.
        assert agreement["ratio"] is None
        assert agreement["judged"] == 0

    def test_an_agreeing_annotation_is_not_counted(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
        run_metric,
    ):
        pass_status, _ = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        result = _result_scored_by(
            test_db, run_metric, test_organization, authenticated_user, db_project, passed=True
        )
        _overrule(authenticated_client, result.id, run_metric.name, pass_status.id, "right call")

        assert self._agreement(authenticated_client, run_metric.id)["disagreements_in_runs"] == 0

    def test_the_count_is_not_capped_like_the_prompt(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
        run_metric,
    ):
        """The cap exists to bound a prompt. A figure on a card is one integer,
        so capping it would understate the problem for no reason."""
        _, fail_status = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        over_the_cap = RUN_REJECTION_LIMIT + 2
        for index in range(over_the_cap):
            result = _result_scored_by(
                test_db,
                run_metric,
                test_organization,
                authenticated_user,
                db_project,
                output=f"{RUN_OUTPUT} ({index})",
            )
            _overrule(
                authenticated_client,
                result.id,
                run_metric.name,
                fail_status.id,
                f"{OVERRULING_COMMENT} ({index})",
            )

        agreement = self._agreement(authenticated_client, run_metric.id)

        assert agreement["disagreements_in_runs"] == over_the_cap


class TestTheCapIsReportedNotHidden:
    """The module takes the position that silently dropping a rejection is the
    one thing this must not do. Run annotations are unbounded, so they are capped
    -- and the count says how many exist, so the drop is visible."""

    def test_the_count_found_exceeds_the_count_sent(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
        run_metric,
        generation_model,  # noqa: F811
    ):
        _, fail_status = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        over_the_cap = RUN_REJECTION_LIMIT + 3
        for index in range(over_the_cap):
            result = _result_scored_by(
                test_db,
                run_metric,
                test_organization,
                authenticated_user,
                db_project,
                output=f"{RUN_OUTPUT} ({index})",
            )
            _overrule(
                authenticated_client,
                result.id,
                run_metric.name,
                fail_status.id,
                f"{OVERRULING_COMMENT} ({index})",
            )

        body = _improve(authenticated_client, run_metric.id).json()

        assert body["run_rejections_used"] == RUN_REJECTION_LIMIT
        assert body["run_rejections_found"] == over_the_cap

    def test_the_prompt_says_some_were_left_out(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
        run_metric,
        generation_model,  # noqa: F811
    ):
        """Otherwise the model reads a sample as the whole picture and writes a
        rewrite claiming to answer every objection."""
        _, fail_status = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        for index in range(RUN_REJECTION_LIMIT + 1):
            result = _result_scored_by(
                test_db,
                run_metric,
                test_organization,
                authenticated_user,
                db_project,
                output=f"{RUN_OUTPUT} ({index})",
            )
            _overrule(
                authenticated_client,
                result.id,
                run_metric.name,
                fail_status.id,
                f"{OVERRULING_COMMENT} ({index})",
            )

        _improve(authenticated_client, run_metric.id)

        assert "are not shown here" in generation_model.prompt

    def test_nothing_is_said_when_nothing_was_left_out(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
        run_metric,
        generation_model,  # noqa: F811
    ):
        _, fail_status = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        result = _result_scored_by(
            test_db, run_metric, test_organization, authenticated_user, db_project
        )
        _overrule(
            authenticated_client, result.id, run_metric.name, fail_status.id, OVERRULING_COMMENT
        )

        _improve(authenticated_client, run_metric.id)

        assert "are not shown here" not in generation_model.prompt
