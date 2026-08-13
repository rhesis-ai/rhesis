"""Integration tests for tuning runs — running a metric over its own cases.

Tests the two run endpoints:
- POST /metrics/{metric_id}/tuning/run
- GET  /metrics/{metric_id}/tuning/run

plus what a run leaves behind on the case list.

The metric invocation is stubbed throughout, which is what makes these
deterministic and free of LLM calls. Celery is stubbed too: this codebase tests
background work by mocking the dispatch and calling the service the task would
have called, rather than by running a broker.

The test that matters most is ``test_the_metric_never_sees_the_expected_verdict``.
Route the metric under test through the normal evaluation path and it is handed
the answer key; nothing raises, the numbers just come out flattering. That test
is the only thing that fails loudly when someone reconnects the wire.

Run with: python -m pytest tests/backend/routes/test_metric_tuning_runs.py -v
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.schemas.metric import MetricScope
from rhesis.backend.app.services import metric_tuning as service
from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup

CASE_INPUT = "How are you?"
CASE_OUTPUT = "I am fine you fucking basterd"
CASE_EXPECTED_OUTPUT = "I am fine, thanks for asking."
# The expected verdict — the answer key. The metric must never be shown this.
CASE_EXPECTED = "fail"
CASE_RATIONALE = "the metric scored 0, but this is toxic so it should be 1"


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
    metric = models.Metric(
        name=name,
        description="Metric under tuning",
        evaluation_prompt="Score how toxic the answer is.",
        score_type=score_type,
        metric_scope=[MetricScope.SINGLE_TURN.value],
        backend_type_id=backend_type_lookup.id,
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
def no_dispatch():
    """Stop the route from actually queueing the background task.

    Yields the mock so a test can assert the run was dispatched exactly once
    with the metric it was asked for.
    """
    with patch("rhesis.backend.app.routers.metric_tuning.task_launcher") as launcher:
        yield launcher


def _create_case(client: TestClient, metric_id, **overrides) -> dict:
    body = {
        "input": CASE_INPUT,
        "output": CASE_OUTPUT,
        "expected_output": CASE_EXPECTED_OUTPUT,
        "expected": CASE_EXPECTED,
        "rationale": CASE_RATIONALE,
    }
    body.update(overrides)
    response = client.post(f"/metrics/{metric_id}/tuning/cases", json=body)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


def _evaluator_returning(*results):
    """A stubbed MetricEvaluator whose evaluate() yields the given results in order.

    Each entry is either a result dict or an exception to raise. The mock is
    returned so tests can inspect the arguments the metric was invoked with.
    """
    calls = list(results)
    evaluator = MagicMock()

    def _evaluate(**kwargs):
        outcome = calls.pop(0) if calls else {"score": 0.0, "reason": "no more stubs"}
        if isinstance(outcome, Exception):
            raise outcome
        return {"Metric": outcome}

    evaluator.evaluate.side_effect = _evaluate
    factory = MagicMock(return_value=evaluator)
    return factory, evaluator


def _run(test_db: Session, metric: models.Metric, org_id, *results):
    """Execute a run with the metric invocation stubbed. Returns the evaluator mock."""
    factory, evaluator = _evaluator_returning(*results)
    with patch("rhesis.backend.metrics.evaluator.MetricEvaluator", factory):
        service.execute_tuning_run(test_db, metric, org_id)
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

    def test_a_numeric_metrics_verdict_is_its_number(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        numeric_metric: models.Metric,
    ):
        _create_case(authenticated_client, numeric_metric.id, expected="0.8")
        _run(test_db, numeric_metric, test_org_id, {"score": 0.79, "reason": "close"})

        cases = authenticated_client.get(f"/metrics/{numeric_metric.id}/tuning/cases").json()

        assert cases[0]["result"]["verdict"] == "0.79"

    def test_the_metric_never_sees_the_expected_verdict(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """The one that stops a flattering, meaningless scorecard.

        The metric is invoked as the system under test: it gets the case payload
        and nothing else. `expected_output` is the case's own expected output —
        never `prompt.expected_response`, which holds the expected verdict.
        """
        _create_case(authenticated_client, tuning_metric.id)
        evaluator = _run(test_db, tuning_metric, test_org_id, {"score": 0.0, "reason": "toxic"})

        kwargs = evaluator.evaluate.call_args.kwargs
        assert kwargs["input_text"] == CASE_INPUT
        assert kwargs["output_text"] == CASE_OUTPUT
        assert kwargs["expected_output"] == CASE_EXPECTED_OUTPUT
        # The verdict and the reviewer's rationale reach the metric nowhere at all.
        passed = " ".join(str(v) for v in kwargs.values())
        assert CASE_EXPECTED not in passed
        assert CASE_RATIONALE not in passed

    def test_a_failed_call_is_errored_and_the_run_continues(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """A flaky provider must never read as a bad metric."""
        _create_case(authenticated_client, tuning_metric.id)
        _create_case(authenticated_client, tuning_metric.id, input="The second one")

        _run(
            test_db,
            tuning_metric,
            test_org_id,
            RuntimeError("provider unreachable"),
            {"score": 1.0, "reason": "fine"},
        )

        cases = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/cases").json()
        assert cases[0]["result"]["error"] == "provider unreachable"
        assert cases[0]["result"]["verdict"] is None
        # The run carried on rather than stopping at the first failure.
        assert cases[1]["result"]["verdict"] == "pass"

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

    def test_running_does_not_modify_the_cases(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id,
        tuning_metric: models.Metric,
    ):
        """Scoring must never edit the thing being scored."""
        before = _create_case(authenticated_client, tuning_metric.id)
        _run(test_db, tuning_metric, test_org_id, {"score": 1.0, "reason": "fine"})

        after = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/cases").json()[0]

        for field in ("input", "output", "expected_output", "expected", "rationale"):
            assert after[field] == before[field], field

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
