"""Integration tests for tuning runs — running a metric over its own cases.

Tests the two run endpoints:
- POST /metrics/{metric_id}/tuning/run
- GET  /metrics/{metric_id}/tuning/run

plus what a run leaves behind on the case list.

The metric invocation is stubbed throughout, which is what makes these
deterministic and free of LLM calls. Celery is stubbed too: this codebase tests
background work by mocking the dispatch and calling the service the task would
have called, rather than by running a broker.

The test that matters most is ``test_the_metric_sees_the_case_and_nothing_else``.
The metric under test occupies the endpoint's slot: route it through the normal
evaluation path instead and it is read at the wrong level, which is how a
reviewer's words or a stored verdict reach a metric that is meant to be judged on
its own. Nothing raises, the numbers just come out flattering. That test is the
only thing in here that fails loudly when someone reconnects the wire.

Run with: python -m pytest tests/backend/routes/test_metric_tuning_runs.py -v
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud import metric_tuning as crud_metric_tuning
from rhesis.backend.app.schemas.metric import MetricScope
from rhesis.backend.app.schemas.metric_tuning_metadata import (
    MetricTuningRunSummary,
    TuningRunStatus,
)
from rhesis.backend.app.services import metric_tuning as service
from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup
from rhesis.backend.metrics.result_builder import MetricResultBuilder

CASE_INPUT = "How are you?"
CASE_OUTPUT = "I am fine you fucking basterd"
CASE_REFERENCE_ANSWER = "I am fine, thanks for asking."
# What a reviewer wrote about the metric. It must never reach the metric.
REVIEW_COMMENT = "the metric called this harmless, but it is plainly toxic"


def _make_model(db: Session, organization_id, user_id) -> models.Model:
    """A judging model for a metric — or for the evaluation setting — to point at.

    A run resolves the metric's own model, else the configured default
    evaluation model, and refuses if there is neither. So every runnable metric
    here needs one of the two.
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
    with_model: bool = True,
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
    model = _make_model(db, organization_id, user_id) if with_model else None
    metric = models.Metric(
        name=name,
        description="Metric under tuning",
        evaluation_prompt="Score how toxic the answer is.",
        score_type=score_type,
        metric_scope=[MetricScope.SINGLE_TURN.value],
        backend_type_id=backend_type_lookup.id,
        model_id=model.id if model else None,
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
        test_db, f"Toxicity Run {uuid.uuid4().hex[:6]}", test_org_id, authenticated_user_id
    )


@pytest.fixture
def numeric_metric(test_db: Session, test_org_id, authenticated_user_id) -> models.Metric:
    return _make_metric(
        test_db,
        f"Numeric Run {uuid.uuid4().hex[:6]}",
        test_org_id,
        authenticated_user_id,
        score_type="numeric",
        min_score=0.0,
        max_score=1.0,
        threshold=0.5,
    )


@pytest.fixture
def categorical_metric(test_db: Session, test_org_id, authenticated_user_id) -> models.Metric:
    return _make_metric(
        test_db,
        f"Categorical Run {uuid.uuid4().hex[:6]}",
        test_org_id,
        authenticated_user_id,
        score_type="categorical",
        categories=["helpful", "harmful"],
        passing_categories=["helpful"],
    )


@pytest.fixture
def error_category_metric(test_db: Session, test_org_id, authenticated_user_id) -> models.Metric:
    """A metric that answers ``error`` as a real category, not as a failure."""
    return _make_metric(
        test_db,
        f"Error Category Run {uuid.uuid4().hex[:6]}",
        test_org_id,
        authenticated_user_id,
        score_type="categorical",
        categories=["ok", "error"],
        passing_categories=["ok"],
    )


@pytest.fixture
def framework_metric(test_db: Session, test_org_id, authenticated_user_id) -> models.Metric:
    """A framework-provided metric — its prompt is not the org's to tune."""
    return _make_metric(
        test_db,
        f"Framework Run {uuid.uuid4().hex[:6]}",
        test_org_id,
        authenticated_user_id,
        backend_type="deepeval",
    )


@pytest.fixture
def metric_without_model(test_db: Session, test_org_id, authenticated_user_id) -> models.Metric:
    """A metric with no judging model — nothing to run it with."""
    return _make_metric(
        test_db,
        f"Modelless {uuid.uuid4().hex[:6]}",
        test_org_id,
        authenticated_user_id,
        with_model=False,
    )


def _set_evaluation_model(db: Session, user_id, model_id) -> None:
    """Point the default evaluation model at ``model_id`` (or clear it).

    Goes through ``user.settings.update`` rather than writing the column: the
    settings manager is cached per User instance, so a raw column write can be
    read back stale.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    user.settings.update(
        {"models": {"evaluation": {"model_id": str(model_id) if model_id else None}}}
    )
    db.flush()
    db.commit()


@pytest.fixture
def no_dispatch():
    """Stop the route from actually queueing the background task.

    Yields the mock so a test can assert the run was dispatched exactly once
    with the metric it was asked for.
    """
    with patch("rhesis.backend.app.routers.metric_tuning.launch_job") as launcher:
        yield launcher


@pytest.fixture
def broken_dispatch():
    """Dispatch that raises, the way an unreachable broker does.

    The claim is committed before this is called, so what the route does with the
    failure is the whole question.
    """
    with patch(
        "rhesis.backend.app.routers.metric_tuning.task_launcher",
        side_effect=RuntimeError("broker unreachable"),
    ) as launcher:
        yield launcher


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


def _local_strategy_result(score, reason: str) -> dict:
    """What the local strategy actually hands back for a completed evaluation.

    Built with the real builder rather than a hand-written dict, because the
    thing under test is a property of the real shape: the SDK reports its own
    failures as a *result*, the local strategy wraps that in ``success()``, and
    ``success()`` has no ``error`` key to find. Stubbing the connector's shape
    instead is what let this go unnoticed.
    """
    result = MetricResultBuilder.success(
        score=score,
        reason=reason,
        is_successful=False,
        backend="rhesis",
        name="Metric",
        class_name="CategoricalJudge",
    )
    assert "error" not in result, "the premise of these tests"
    return result


def _evaluator_returning(*results, by_input=None):
    """A stubbed MetricEvaluator whose evaluate() yields the given results in order.

    Each entry is either a result dict or an exception to raise. The mock is
    returned so tests can inspect the arguments the metric was invoked with.

    ``by_input`` keys the results on the case's input instead. Call order is not
    insertion order: every case created in one test shares a ``created_at``,
    since the requests run inside the test's single transaction, so a test that
    needs a particular score on a particular case has to say which case.
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
    factory = MagicMock(return_value=evaluator)
    return factory, evaluator


def _cases_by_id(client: TestClient, metric_id) -> dict:
    """Every case, keyed by its own id rather than read by list position."""
    response = client.get(f"/metrics/{metric_id}/tuning/cases")
    assert response.status_code == status.HTTP_200_OK, response.text
    return {case["id"]: case for case in response.json()}


def _review(client: TestClient, metric_id, case_id, decision: str, comment=None) -> dict:
    """Record one judgement of what the metric said about a case."""
    body = {"decision": decision}
    if comment is not None:
        body["comment"] = comment
    response = client.post(f"/metrics/{metric_id}/tuning/cases/{case_id}/review", json=body)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


def _stored_reviews(db: Session, case_id) -> list:
    """The case's review history straight out of the JSONB, oldest first.

    Read raw rather than through the API because the API only exposes the review
    that currently stands — an invalidated one is still in storage, comment and
    all, and that is the point of these tests.
    """
    db.expire_all()
    db_test = db.query(models.Test).filter(models.Test.id == uuid.UUID(str(case_id))).first()
    return (db_test.test_metadata or {}).get("reviews", [])


def _claim(
    test_db: Session,
    metric: models.Metric,
    org_id,
    *,
    last_advanced: timedelta = timedelta(seconds=0),
    heartbeat: bool = True,
) -> None:
    """Leave a ``running`` claim behind, the way a worker that died would.

    ``last_advanced`` is how long ago the run last got anywhere. ``heartbeat``
    off writes the claim without ``progressed_at``, which is what a claim made
    before that field existed looks like.
    """
    test_set = service.get_tuning_test_set(test_db, metric.id, org_id)
    when = (datetime.now(timezone.utc) - last_advanced).isoformat()
    summary = MetricTuningRunSummary(
        status=TuningRunStatus.RUNNING,
        started_at=when,
        progressed_at=when if heartbeat else None,
        total_cases=1,
    )
    crud_metric_tuning.set_run_summary(test_db, test_set, summary)
    test_db.commit()


def _run(test_db: Session, metric: models.Metric, org_id, *results, user_id=None, by_input=None):
    """Execute a run with the metric invocation stubbed. Returns the evaluator mock.

    Expires the session first because reviews are written by a request on its own
    session. Without it this session serves the rows it cached before that commit
    and the run rewrites them from stale metadata — a background worker always
    starts from a fresh session.
    """
    test_db.expire_all()
    factory, evaluator = _evaluator_returning(*results, by_input=by_input)
    with patch("rhesis.backend.metrics.evaluator.MetricEvaluator", factory):
        service.execute_tuning_run(test_db, metric, org_id, user_id)
    # Kept on the mock so a test can assert how the evaluator was constructed,
    # not just what it was asked to evaluate.
    evaluator.constructed_with = factory.call_args
    return evaluator


@pytest.mark.integration
@pytest.mark.routes
class TestStartTuningRun:
    """POST /metrics/{metric_id}/tuning/run"""

    def test_a_metric_with_no_cases_is_told_to_add_some(
        self,
        authenticated_client: TestClient,
        tuning_metric: models.Metric,
        no_dispatch,
    ):
        """An empty scorecard would say nothing; the refusal says what to do."""
        response = authenticated_client.post(f"/metrics/{tuning_metric.id}/tuning/run")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "tuning case" in response.json()["detail"].lower()
        no_dispatch.assert_not_called()

    def test_starting_a_run_reports_it_in_progress(
        self,
        authenticated_client: TestClient,
        tuning_metric: models.Metric,
        no_dispatch,
    ):
        _create_case(authenticated_client, tuning_metric.id)
        _create_case(authenticated_client, tuning_metric.id, input="Another one")

        response = authenticated_client.post(f"/metrics/{tuning_metric.id}/tuning/run")

        assert response.status_code == status.HTTP_202_ACCEPTED
        body = response.json()
        assert body["status"] == "running"
        assert body["total_cases"] == 2
        assert body["completed_cases"] == 0
        assert body["started_at"]

    def test_starting_a_run_queues_the_background_work(
        self,
        authenticated_client: TestClient,
        tuning_metric: models.Metric,
        no_dispatch,
    ):
        """Thirty cases is thirty LLM calls — the browser does not wait for them."""
        _create_case(authenticated_client, tuning_metric.id)

        authenticated_client.post(f"/metrics/{tuning_metric.id}/tuning/run")

        assert no_dispatch.call_count == 1
        assert str(tuning_metric.id) in no_dispatch.call_args.args

    def test_a_second_run_is_refused_while_one_is_going(
        self,
        authenticated_client: TestClient,
        tuning_metric: models.Metric,
        no_dispatch,
    ):
        _create_case(authenticated_client, tuning_metric.id)
        authenticated_client.post(f"/metrics/{tuning_metric.id}/tuning/run")

        response = authenticated_client.post(f"/metrics/{tuning_metric.id}/tuning/run")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert no_dispatch.call_count == 1

    def test_a_framework_metric_cannot_be_run(
        self,
        authenticated_client: TestClient,
        framework_metric: models.Metric,
        no_dispatch,
    ):
        """Refused in the API, not only by hiding the button."""
        response = authenticated_client.post(f"/metrics/{framework_metric.id}/tuning/run")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "custom" in response.json()["detail"].lower()
        no_dispatch.assert_not_called()

    def test_unknown_metric_404s(self, authenticated_client: TestClient, no_dispatch):
        response = authenticated_client.post(f"/metrics/{uuid.uuid4()}/tuning/run")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_a_metric_with_no_model_falls_back_to_the_evaluation_default(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        authenticated_user_id,
        metric_without_model: models.Metric,
        no_dispatch,
    ):
        """Step two of the chain: the model configured as the evaluation default."""
        _create_case(authenticated_client, metric_without_model.id)
        default_model = _make_model(test_db, test_org_id, authenticated_user_id)
        _set_evaluation_model(test_db, authenticated_user_id, default_model.id)

        response = authenticated_client.post(f"/metrics/{metric_without_model.id}/tuning/run")

        assert response.status_code == status.HTTP_202_ACCEPTED, response.text
        assert no_dispatch.call_count == 1

    def test_neither_a_metric_model_nor_an_evaluation_default_is_refused(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        authenticated_user_id,
        metric_without_model: models.Metric,
        no_dispatch,
    ):
        """Where the chain ends: an error, not a third silent step.

        The evaluation path keeps going past here — to whatever the caller
        passed, then to the SDK's own hosted default. A scorecard produced by a
        judge nobody chose measures nothing, so the run is refused instead.
        """
        _create_case(authenticated_client, metric_without_model.id)
        _set_evaluation_model(test_db, authenticated_user_id, None)

        response = authenticated_client.post(f"/metrics/{metric_without_model.id}/tuning/run")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "model" in response.json()["detail"].lower()
        no_dispatch.assert_not_called()

    def test_an_unreadable_evaluation_model_setting_is_still_a_refusal(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        authenticated_user_id,
        metric_without_model: models.Metric,
        no_dispatch,
    ):
        """A broken setting must refuse like a missing one, not crash.

        The settings accessor parses the stored value as a UUID, so a malformed
        one raises rather than reading as absent — and the walk that reads it
        only guards against a missing attribute. Unhandled it escapes as a 500
        from the very function whose job is to refuse cleanly.
        """
        _create_case(authenticated_client, metric_without_model.id)
        user = test_db.query(models.User).filter(models.User.id == authenticated_user_id).first()
        user.settings.update({"models": {"evaluation": {"model_id": "not-a-uuid"}}})
        test_db.flush()
        test_db.commit()

        response = authenticated_client.post(f"/metrics/{metric_without_model.id}/tuning/run")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "model" in response.json()["detail"].lower()
        no_dispatch.assert_not_called()

    def test_the_refusal_leaves_no_run_behind(
        self,
        authenticated_client: TestClient,
        metric_without_model: models.Metric,
        no_dispatch,
    ):
        """Refused before anything is claimed, so the status is untouched."""
        _create_case(authenticated_client, metric_without_model.id)
        authenticated_client.post(f"/metrics/{metric_without_model.id}/tuning/run")

        body = authenticated_client.get(f"/metrics/{metric_without_model.id}/tuning/run").json()

        assert body["status"] == "never_run"


@pytest.mark.integration
@pytest.mark.routes
class TestReadTuningRun:
    """GET /metrics/{metric_id}/tuning/run"""

    def test_a_metric_never_run_reads_as_never_run(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        """One shape either way, so the tab has nothing to branch on."""
        response = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/run")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "never_run"

    def test_reports_when_the_last_run_finished(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
        no_dispatch,
    ):
        _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, {"score": 0.0, "reason": "toxic"})

        body = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/run").json()

        assert body["status"] == "completed"
        assert body["completed_at"]
        assert body["total_cases"] == 1
        assert body["completed_cases"] == 1

    def test_a_framework_metric_cannot_be_read(
        self, authenticated_client: TestClient, framework_metric: models.Metric
    ):
        response = authenticated_client.get(f"/metrics/{framework_metric.id}/tuning/run")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.integration
@pytest.mark.routes
class TestRunResults:
    """What a finished run leaves on the cases."""

    def test_each_case_shows_the_metrics_verdict_and_reasoning(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        _create_case(authenticated_client, tuning_metric.id)
        _run(
            test_db,
            tuning_metric,
            test_org_id,
            {"score": 1.0, "reason": "No insult detected."},
        )

        cases = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/cases").json()

        assert cases[0]["result"]["verdict"] == "pass"
        assert cases[0]["result"]["reasoning"] == "No insult detected."
        assert cases[0]["result"]["error"] is None
        assert cases[0]["result"]["evaluated_at"]

    def test_the_metric_is_judged_with_its_own_model(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """An explicit model reaches the evaluator, so it never picks one itself.

        `MetricEvaluator` falls back to the SDK's built-in default when no model
        is passed. Passing one is what removes that possibility — there is no
        argument left to omit.
        """
        _create_case(authenticated_client, tuning_metric.id)
        evaluator = _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "ok"})

        model = evaluator.constructed_with.kwargs.get("model")
        assert model is not None, "no model passed — the evaluator would pick its own default"

    def test_a_numeric_metrics_verdict_is_its_number(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        numeric_metric: models.Metric,
    ):
        _create_case(authenticated_client, numeric_metric.id)
        _run(test_db, numeric_metric, test_org_id, {"score": 0.79, "reason": "close"})

        cases = authenticated_client.get(f"/metrics/{numeric_metric.id}/tuning/cases").json()

        assert cases[0]["result"]["verdict"] == "0.79"

    def test_the_metric_sees_the_case_and_nothing_else(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """The one that stops a flattering, meaningless scorecard.

        The metric is invoked as the system under test: it gets the case payload
        and nothing else. `expected_output` is the case's own reference answer,
        read out of `prompt.content` — the normal evaluation path would hand it
        `prompt.expected_response`, which this feature never writes, so wiring it
        back up empties this argument and fails here rather than quietly
        flattering the numbers.

        The case is reviewed first so there is human text to leak by the time the
        second run invokes the metric.
        """
        first_reasoning = "the first run judged this harmless"
        case = _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": first_reasoning})
        _review(authenticated_client, tuning_metric.id, case["id"], "rejected", REVIEW_COMMENT)

        evaluator = _run(test_db, tuning_metric, test_org_id, {"score": 0.0, "reason": "toxic"})

        kwargs = evaluator.evaluate.call_args.kwargs
        assert kwargs["input_text"] == CASE_INPUT
        assert kwargs["output_text"] == CASE_OUTPUT
        assert kwargs["expected_output"] == CASE_REFERENCE_ANSWER
        # Neither the reviewer's words nor what the metric said last time reach it.
        passed = " ".join(str(value) for value in kwargs.values())
        assert REVIEW_COMMENT not in passed
        assert first_reasoning not in passed

    def test_a_failed_call_is_errored_and_the_run_continues(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """A flaky provider must never read as a bad metric."""
        errored = _create_case(authenticated_client, tuning_metric.id)
        reached = _create_case(authenticated_client, tuning_metric.id, input="The second one")

        _run(
            test_db,
            tuning_metric,
            test_org_id,
            by_input={
                CASE_INPUT: RuntimeError("provider unreachable"),
                "The second one": {"score": 1.0, "reason": "fine"},
            },
        )

        cases = _cases_by_id(authenticated_client, tuning_metric.id)
        assert cases[errored["id"]]["result"]["error"] == "provider unreachable"
        assert cases[errored["id"]]["result"]["verdict"] is None
        # The run carried on rather than stopping at the failure.
        assert cases[reached["id"]]["result"]["verdict"] == "pass"

        summary = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/run").json()
        assert summary["status"] == "completed"
        assert summary["completed_cases"] == 2
        assert summary["errored_cases"] == 1

    def test_an_error_result_from_the_evaluator_is_errored_too(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """The evaluator reports some failures as a result rather than by raising."""
        _create_case(authenticated_client, tuning_metric.id)
        _run(
            test_db,
            tuning_metric,
            test_org_id,
            {"score": 0.0, "reason": "Evaluation failed", "error": "rate limited"},
        )

        cases = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/cases").json()
        assert cases[0]["result"]["error"] == "rate limited"
        assert cases[0]["result"]["verdict"] is None

    def test_a_provider_failure_the_sdk_reports_as_a_result_is_errored(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        categorical_metric: models.Metric,
    ):
        """The failure that actually happens, in the shape it actually arrives in.

        A 401 against the judging model does not raise and does not set
        ``error``. It comes back as a scored result whose score is the SDK's
        sentinel, and reading that as a verdict is what produced a run of
        "1 cases, 0 errored" with ``error`` stored as the metric's answer.
        """
        _create_case(authenticated_client, categorical_metric.id)

        _run(
            test_db,
            categorical_metric,
            test_org_id,
            _local_strategy_result(
                "error",
                "Error evaluating with Toxicity: AuthenticationError: 401 Unauthorized",
            ),
        )

        cases = authenticated_client.get(f"/metrics/{categorical_metric.id}/tuning/cases").json()
        assert cases[0]["result"]["verdict"] is None
        assert "401" in cases[0]["result"]["error"]

        summary = authenticated_client.get(f"/metrics/{categorical_metric.id}/tuning/run").json()
        assert summary["errored_cases"] == 1

    def test_a_provider_failure_on_a_binary_metric_is_not_recorded_as_a_pass(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """The same failure on a binary metric, where reading it as a verdict flatters.

        ``error`` is a non-empty string and therefore truthy, so the sentinel
        renders as ``pass`` -- an unreachable provider recorded as the metric
        agreeing with the case.
        """
        _create_case(authenticated_client, tuning_metric.id)

        _run(
            test_db,
            tuning_metric,
            test_org_id,
            _local_strategy_result(
                "error", "Error evaluating with Toxicity: AuthenticationError: 401"
            ),
        )

        cases = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/cases").json()
        assert cases[0]["result"]["verdict"] is None, "a failed call is not a passing case"
        assert cases[0]["result"]["error"]

    def test_a_numeric_failure_is_errored_rather_than_a_zero(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        numeric_metric: models.Metric,
    ):
        """A numeric metric's failure sentinel is an ordinary number.

        Nothing in the score distinguishes it from a real 0.0, so the reason the
        SDK writes is the only thing left to go on.
        """
        _create_case(authenticated_client, numeric_metric.id)

        _run(
            test_db,
            numeric_metric,
            test_org_id,
            _local_strategy_result(0.0, "Error evaluating with Relevance: timed out"),
        )

        cases = authenticated_client.get(f"/metrics/{numeric_metric.id}/tuning/cases").json()
        assert cases[0]["result"]["verdict"] is None
        assert cases[0]["result"]["error"] == "Error evaluating with Relevance: timed out"

    def test_a_metric_that_answers_error_as_a_category_keeps_its_verdict(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        error_category_metric: models.Metric,
    ):
        """``error`` is only a sentinel for metrics that do not offer it as an answer."""
        _create_case(authenticated_client, error_category_metric.id)

        _run(
            test_db,
            error_category_metric,
            test_org_id,
            _local_strategy_result("error", "The response reports a system error."),
        )

        cases = authenticated_client.get(f"/metrics/{error_category_metric.id}/tuning/cases").json()
        assert cases[0]["result"]["verdict"] == "error"
        assert cases[0]["result"]["error"] is None

    def test_running_does_not_modify_the_cases(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """Scoring must never edit the thing being scored — payload or reviews."""
        before = _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "fine"})
        _review(authenticated_client, tuning_metric.id, before["id"], "rejected", REVIEW_COMMENT)
        reviews_before = _stored_reviews(test_db, before["id"])

        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "fine again"})

        after = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/cases").json()[0]
        for field in ("input", "output", "reference_answer"):
            assert after[field] == before[field], field
        assert _stored_reviews(test_db, before["id"]) == reviews_before

    def test_only_the_latest_run_is_kept(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, {"score": 0.0, "reason": "first run"})
        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "second run"})

        cases = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/cases").json()

        assert cases[0]["result"]["verdict"] == "pass"
        assert cases[0]["result"]["reasoning"] == "second run"

    def test_a_case_added_after_a_run_has_no_result(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "fine"})

        fresh = _create_case(authenticated_client, tuning_metric.id, input="Added later")

        assert fresh["result"] is None

    def test_a_failed_run_says_so(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """Otherwise old numbers sit there being read as new ones."""
        _create_case(authenticated_client, tuning_metric.id)
        service.fail_tuning_run(test_db, tuning_metric, test_org_id, "worker died")

        body = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/run").json()

        assert body["status"] == "failed"
        assert body["error"] == "worker died"

    def test_a_failed_run_does_not_block_the_next_one(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
        no_dispatch,
    ):
        _create_case(authenticated_client, tuning_metric.id)
        service.fail_tuning_run(test_db, tuning_metric, test_org_id, "worker died")

        response = authenticated_client.post(f"/metrics/{tuning_metric.id}/tuning/run")

        assert response.status_code == status.HTTP_202_ACCEPTED


@pytest.mark.integration
@pytest.mark.routes
class TestRunsAndStandingReviews:
    """What a re-run does to the reviews already on the cases.

    Reviews are human-authored, so a run never clears them. Whether one still
    *stands* is a separate question, re-answered on every read against the
    metric's current threshold: ordinary numeric drift keeps it, crossing the
    threshold drops it, and a `score_type` change drops all of them. The comments
    stay in storage either way.
    """

    def test_a_review_survives_a_re_run_that_did_not_move_the_verdict(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        numeric_metric: models.Metric,
    ):
        """0.79 to 0.81 is arithmetic noise under a 0.5 threshold, not a change.

        Treating it as one would invalidate every review on every run, and no two
        runs would ever be comparable.
        """
        case = _create_case(authenticated_client, numeric_metric.id)
        _run(test_db, numeric_metric, test_org_id, {"score": 0.79, "reason": "mostly relevant"})
        _review(authenticated_client, numeric_metric.id, case["id"], "accepted")

        _run(test_db, numeric_metric, test_org_id, {"score": 0.81, "reason": "still relevant"})

        after = authenticated_client.get(f"/metrics/{numeric_metric.id}/tuning/cases").json()[0]
        assert after["result"]["verdict"] == "0.81"
        assert after["outcome"] == "accepted"
        assert after["unreviewed_reason"] is None
        # Still the verdict the reviewer actually looked at.
        assert after["review"]["verdict"] == "0.79"

    def test_crossing_the_threshold_invalidates_the_review(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        numeric_metric: models.Metric,
    ):
        """The case the edit actually changed comes back for a fresh look."""
        case = _create_case(authenticated_client, numeric_metric.id)
        _run(test_db, numeric_metric, test_org_id, {"score": 0.79, "reason": "mostly relevant"})
        _review(authenticated_client, numeric_metric.id, case["id"], "rejected", REVIEW_COMMENT)

        _run(test_db, numeric_metric, test_org_id, {"score": 0.2, "reason": "off topic now"})

        after = authenticated_client.get(f"/metrics/{numeric_metric.id}/tuning/cases").json()[0]
        assert after["outcome"] == "unreviewed"
        assert after["unreviewed_reason"] == "invalidated"
        assert after["review"] is None
        # Dropped from the outcome, not from storage — the comment is the thing
        # the reviewer reads when rewriting the prompt.
        stored = _stored_reviews(test_db, case["id"])
        assert [review["comment"] for review in stored] == [REVIEW_COMMENT]

    def test_changing_the_score_type_invalidates_every_review(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        numeric_metric: models.Metric,
    ):
        """A stored verdict means something else under a different score type."""
        rejected = _create_case(authenticated_client, numeric_metric.id)
        other = _create_case(authenticated_client, numeric_metric.id, input="The second one")
        _run(
            test_db,
            numeric_metric,
            test_org_id,
            by_input={
                CASE_INPUT: {"score": 0.79, "reason": "mostly relevant"},
                "The second one": {"score": 0.9, "reason": "spot on"},
            },
        )
        _review(authenticated_client, numeric_metric.id, rejected["id"], "rejected", REVIEW_COMMENT)
        accepted = {
            case["id"]: case
            for case in authenticated_client.post(
                f"/metrics/{numeric_metric.id}/tuning/reviews/accept-rest"
            ).json()
        }
        assert accepted[rejected["id"]]["outcome"] == "rejected"
        assert accepted[other["id"]]["outcome"] == "accepted"

        test_db.expire_all()
        metric = test_db.query(models.Metric).filter(models.Metric.id == numeric_metric.id).first()
        metric.score_type = "categorical"
        metric.categories = ["relevant", "irrelevant"]
        metric.passing_categories = ["relevant"]
        test_db.commit()

        cases = authenticated_client.get(f"/metrics/{numeric_metric.id}/tuning/cases").json()
        assert {case["outcome"] for case in cases} == {"unreviewed"}
        assert {case["unreviewed_reason"] for case in cases} == {"invalidated"}
        assert [review["comment"] for review in _stored_reviews(test_db, rejected["id"])] == [
            REVIEW_COMMENT
        ]


@pytest.mark.integration
@pytest.mark.routes
class TestARunThatNeverFinishes:
    """A `running` claim nobody is behind must not wedge the metric forever.

    Only the run itself ever clears its claim, so a worker that dies — or a
    dispatch that never reaches one — leaves the claim standing, every later run
    refused, and the Run button disabled on that same status. There is no reset
    route by design: the claim carries a heartbeat and expires on its own.
    """

    def test_a_stale_claim_does_not_refuse_the_next_run(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
        no_dispatch,
    ):
        """The crashed-worker entrance: recovery used to mean editing the database."""
        _create_case(authenticated_client, tuning_metric.id)
        _claim(test_db, tuning_metric, test_org_id, last_advanced=service.STALE_RUN_AFTER * 2)

        response = authenticated_client.post(f"/metrics/{tuning_metric.id}/tuning/run")

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.json()["status"] == "running"
        assert no_dispatch.call_count == 1

    def test_a_stale_claim_reads_as_failed_rather_than_forever_running(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """Otherwise the interface polls a spinner nothing is behind."""
        _create_case(authenticated_client, tuning_metric.id)
        _claim(test_db, tuning_metric, test_org_id, last_advanced=service.STALE_RUN_AFTER * 2)

        body = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/run").json()

        assert body["status"] == "failed"
        assert body["error"] == service.STALE_RUN_MESSAGE
        assert body["completed_at"] is None

    def test_a_claim_from_before_the_heartbeat_existed_still_expires(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
        no_dispatch,
    ):
        """Nothing migrates the stored summary, so `started_at` has to stand in."""
        _create_case(authenticated_client, tuning_metric.id)
        _claim(
            test_db,
            tuning_metric,
            test_org_id,
            last_advanced=service.STALE_RUN_AFTER * 2,
            heartbeat=False,
        )

        response = authenticated_client.post(f"/metrics/{tuning_metric.id}/tuning/run")

        assert response.status_code == status.HTTP_202_ACCEPTED

    def test_a_run_that_is_still_advancing_is_left_alone(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
        no_dispatch,
    ):
        """The escape hatch must not become a second way to double-run a metric."""
        _create_case(authenticated_client, tuning_metric.id)
        _claim(test_db, tuning_metric, test_org_id, last_advanced=timedelta(seconds=30))

        response = authenticated_client.post(f"/metrics/{tuning_metric.id}/tuning/run")

        assert response.status_code == status.HTTP_409_CONFLICT
        no_dispatch.assert_not_called()
        still = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/run").json()
        assert still["status"] == "running"

    def test_a_long_run_keeps_renewing_its_claim(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """The window covers one case, not the whole set — a run advances the heartbeat."""
        _create_case(authenticated_client, tuning_metric.id)
        _claim(test_db, tuning_metric, test_org_id, last_advanced=service.STALE_RUN_AFTER * 2)

        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "toxic"})

        body = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/run").json()

        assert body["status"] == "completed"

    def test_the_refusal_does_not_disturb_the_run_in_progress(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
        no_dispatch,
    ):
        """A rejected second press must cost the first run nothing."""
        case = _create_case(authenticated_client, tuning_metric.id)
        authenticated_client.post(f"/metrics/{tuning_metric.id}/tuning/run")

        refused = authenticated_client.post(f"/metrics/{tuning_metric.id}/tuning/run")
        assert refused.status_code == status.HTTP_409_CONFLICT

        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "toxic"})

        body = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/run").json()
        assert body["status"] == "completed"
        assert body["completed_cases"] == 1
        assert body["errored_cases"] == 0
        result = _cases_by_id(authenticated_client, tuning_metric.id)[case["id"]]["result"]
        assert result["reasoning"] == "toxic"


@pytest.mark.integration
@pytest.mark.routes
class TestADispatchThatNeverReachesAWorker:
    """The claim is committed before dispatch, so a broker failure needs releasing.

    This is the second entrance to the same wedge, and the one that does not need
    waiting out: the request itself knows no run is coming.
    """

    def test_a_dispatch_failure_is_reported_rather_than_read_as_started(
        self,
        authenticated_client: TestClient,
        tuning_metric: models.Metric,
        broken_dispatch,
    ):
        _create_case(authenticated_client, tuning_metric.id)

        response = authenticated_client.post(f"/metrics/{tuning_metric.id}/tuning/run")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "broker" not in response.text, "the broker's own words are not the caller's business"

    def test_a_dispatch_failure_leaves_no_run_in_flight(
        self,
        authenticated_client: TestClient,
        tuning_metric: models.Metric,
        broken_dispatch,
    ):
        _create_case(authenticated_client, tuning_metric.id)
        authenticated_client.post(f"/metrics/{tuning_metric.id}/tuning/run")

        body = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/run").json()

        assert body["status"] == "failed"
        assert body["error"]

    def test_the_next_run_is_not_refused(
        self,
        authenticated_client: TestClient,
        tuning_metric: models.Metric,
        no_dispatch,
    ):
        """Waiting out the staleness window for a run never queued is not recovery."""
        _create_case(authenticated_client, tuning_metric.id)
        with patch(
            "rhesis.backend.app.routers.metric_tuning.task_launcher",
            side_effect=RuntimeError("broker unreachable"),
        ):
            authenticated_client.post(f"/metrics/{tuning_metric.id}/tuning/run")

        response = authenticated_client.post(f"/metrics/{tuning_metric.id}/tuning/run")

        assert response.status_code == status.HTTP_202_ACCEPTED
