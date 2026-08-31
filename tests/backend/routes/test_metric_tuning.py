"""
Integration tests for metric tuning route endpoints.

Tests the HTTP endpoints:
- GET    /metrics/{metric_id}/tuning/cases
- POST   /metrics/{metric_id}/tuning/cases
- PUT    /metrics/{metric_id}/tuning/cases/{case_id}
- DELETE /metrics/{metric_id}/tuning/cases/{case_id}

A case is a situation the metric has to get right -- an input, the answer being
judged and, where the metric needs one, a reference answer. It records no
expected verdict; the judgement happens after a run, through the review routes
(domain.local/adr/0005).

Plus the visibility contract these rows depend on: a tuning test set must not
appear in GET /test_sets and must not be reachable at GET /test_sets/{id}, a
tuning case must not appear in GET /tests nor be reachable at GET /tests/{id},
and the X-Total-Count header must agree with the rows actually returned.

Run with: python -m pytest tests/backend/routes/test_metric_tuning.py -v
"""

import json
import uuid

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, joinedload

from rhesis.backend.app import models
from rhesis.backend.app.schemas.metric import MetricScope
from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup

# The case from the roadmap: a toxicity metric that let an insult through.
CASE_INPUT = "How are you?"
CASE_OUTPUT = "I am fine you fucking basterd"
CASE_REFERENCE_ANSWER = "I am fine, thanks for asking."


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
    """Create a bare metric row (name/evaluation_prompt/score_type are NOT NULL).

    ``backend_type`` matters: only custom metrics can be tuned, so a metric
    without it would be refused by every route here.
    """
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
        # NOT NULL since 82881df987af; a tuning case is one judged (input, output)
        # pair, which is exactly the single-turn shape.
        metric_scope=[MetricScope.SINGLE_TURN.value],
        backend_type_id=backend_type_lookup.id,
        organization_id=organization_id,
        user_id=user_id,
        **columns,
    )
    db.add(metric)
    db.flush()
    return metric


def _persist(db: Session, metric: models.Metric) -> models.Metric:
    db.commit()
    db.refresh(metric)
    return metric


@pytest.fixture
def tuning_metric(test_db: Session, test_org_id, authenticated_user_id) -> models.Metric:
    """A binary custom metric with no tuning test set yet."""
    metric = _make_metric(
        test_db, f"Toxicity Tuning {uuid.uuid4().hex[:6]}", test_org_id, authenticated_user_id
    )
    return _persist(test_db, metric)


@pytest.fixture
def other_metric(test_db: Session, test_org_id, authenticated_user_id) -> models.Metric:
    """A second metric, for cross-metric isolation checks."""
    metric = _make_metric(
        test_db, f"Other Metric {uuid.uuid4().hex[:6]}", test_org_id, authenticated_user_id
    )
    return _persist(test_db, metric)


@pytest.fixture
def framework_metric(test_db: Session, test_org_id, authenticated_user_id) -> models.Metric:
    """A metric provided by a framework -- its prompt is not the org's to tune."""
    metric = _make_metric(
        test_db,
        f"Framework Metric {uuid.uuid4().hex[:6]}",
        test_org_id,
        authenticated_user_id,
        backend_type="deepeval",
    )
    return _persist(test_db, metric)


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


def _load_case(db: Session, case_id) -> models.Test:
    return (
        db.query(models.Test)
        .options(joinedload(models.Test.prompt))
        .filter(models.Test.id == case_id)
        .one()
    )


@pytest.mark.integration
class TestListTuningCases:
    """GET /metrics/{metric_id}/tuning/cases"""

    def test_empty_before_any_case_exists(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        """A metric nobody has tuned returns an empty list, not a 404."""
        response = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/cases")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_get_does_not_create_a_test_set(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        """Reading must not have side effects -- the set is created on first POST."""
        authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/cases")

        assert (
            test_db.query(models.TestSet)
            .filter(models.TestSet.metric_id == tuning_metric.id)
            .first()
            is None
        )

    def test_unknown_metric_404s(self, authenticated_client: TestClient):
        response = authenticated_client.get(f"/metrics/{uuid.uuid4()}/tuning/cases")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_lists_created_cases(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        created = _create_case(authenticated_client, tuning_metric.id)

        response = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/cases")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert [item["id"] for item in data] == [created["id"]]

    def test_does_not_leak_other_metrics_cases(
        self,
        authenticated_client: TestClient,
        tuning_metric: models.Metric,
        other_metric: models.Metric,
    ):
        mine = _create_case(authenticated_client, tuning_metric.id)
        theirs = _create_case(authenticated_client, other_metric.id, input="Different case")

        response = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/cases")

        ids = {item["id"] for item in response.json()}
        assert mine["id"] in ids
        assert theirs["id"] not in ids


@pytest.mark.integration
class TestOnlyCustomMetricsCanBeTuned:
    """A framework-provided metric has no prompt the organization owns."""

    def test_list_refuses_a_framework_metric(
        self, authenticated_client: TestClient, framework_metric: models.Metric
    ):
        response = authenticated_client.get(f"/metrics/{framework_metric.id}/tuning/cases")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "custom" in response.json()["detail"].lower()

    def test_create_refuses_a_framework_metric(
        self, authenticated_client: TestClient, framework_metric: models.Metric
    ):
        response = authenticated_client.post(
            f"/metrics/{framework_metric.id}/tuning/cases",
            json={"input": CASE_INPUT, "output": CASE_OUTPUT},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_refusal_creates_nothing(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        framework_metric: models.Metric,
    ):
        authenticated_client.post(
            f"/metrics/{framework_metric.id}/tuning/cases",
            json={"input": CASE_INPUT, "output": CASE_OUTPUT},
        )

        assert (
            test_db.query(models.TestSet)
            .filter(models.TestSet.metric_id == framework_metric.id)
            .first()
            is None
        )


@pytest.mark.integration
class TestCreateTuningCase:
    """POST /metrics/{metric_id}/tuning/cases"""

    def test_returns_the_case_it_stored(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        data = _create_case(authenticated_client, tuning_metric.id)

        assert data["input"] == CASE_INPUT
        assert data["output"] == CASE_OUTPUT
        assert data["reference_answer"] == CASE_REFERENCE_ANSWER

    def test_the_input_and_the_answer_being_judged_are_enough(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        """Plenty of metrics judge an answer without a reference to compare to."""
        response = authenticated_client.post(
            f"/metrics/{tuning_metric.id}/tuning/cases",
            json={"input": CASE_INPUT, "output": CASE_OUTPUT},
        )

        assert response.status_code == status.HTTP_201_CREATED, response.text
        data = response.json()
        assert data["input"] == CASE_INPUT
        assert data["output"] == CASE_OUTPUT
        assert data["reference_answer"] is None

    def test_creates_the_tuning_test_set_owned_by_the_metric(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        _create_case(authenticated_client, tuning_metric.id)

        test_set = (
            test_db.query(models.TestSet).filter(models.TestSet.metric_id == tuning_metric.id).one()
        )
        assert tuning_metric.name in test_set.name

    def test_reuses_the_test_set_for_later_cases(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        """The set is created once, lazily -- a second case must not make another."""
        _create_case(authenticated_client, tuning_metric.id)
        _create_case(authenticated_client, tuning_metric.id, input="Second case")

        sets = (
            test_db.query(models.TestSet).filter(models.TestSet.metric_id == tuning_metric.id).all()
        )
        assert len(sets) == 1

    def test_the_test_set_carries_no_metric(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        """A tuning test set carries no metric at all, permanently.

        A run invokes the metric under tuning directly (ADR-0004), so nothing is
        waiting to be attached here. The placeholder that used to hold the slot
        open was a metric row that computed nothing and showed up in the
        organization's metric library."""
        _create_case(authenticated_client, tuning_metric.id)

        test_set = (
            test_db.query(models.TestSet)
            .options(joinedload(models.TestSet.metrics))
            .filter(models.TestSet.metric_id == tuning_metric.id)
            .one()
        )
        assert list(test_set.metrics) == []

    def test_stores_the_whole_case_payload_in_prompt_content(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        """prompt.content is what the system under test receives, and here the
        system under test is the metric -- so it gets the whole case, and only
        the case."""
        data = _create_case(authenticated_client, tuning_metric.id)

        payload = json.loads(_load_case(test_db, data["id"]).prompt.content)
        assert payload == {
            "input": CASE_INPUT,
            "output": CASE_OUTPUT,
            "reference_answer": CASE_REFERENCE_ANSWER,
        }

    def test_expected_response_is_left_null(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        """The column that would hand the metric an answer key stays empty.

        It held the expected verdict until ADR-0005 retired that model. Anything
        written here reaches the metric through the normal evaluation path as a
        reference, and nothing raises -- the numbers just come out flattering."""
        data = _create_case(authenticated_client, tuning_metric.id)

        assert _load_case(test_db, data["id"]).prompt.expected_response is None

    def test_metadata_starts_with_no_result_and_no_reviews(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        """The case text lives in the payload; the JSONB is for what comes after."""
        data = _create_case(authenticated_client, tuning_metric.id)

        metadata = _load_case(test_db, data["id"]).test_metadata
        assert metadata == {"reviews": []}

    def test_marks_the_case_as_metric_owned(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        data = _create_case(authenticated_client, tuning_metric.id)

        db_test = test_db.query(models.Test).filter(models.Test.id == data["id"]).one()
        assert db_test.metric_id == tuning_metric.id

    def test_does_not_invent_taxonomy_rows(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        """Tuning cases carry no requirement/category/topic, so none get created."""
        data = _create_case(authenticated_client, tuning_metric.id)

        db_test = test_db.query(models.Test).filter(models.Test.id == data["id"]).one()
        assert db_test.requirement_id is None
        assert db_test.category_id is None
        assert db_test.topic_id is None

    def test_input_is_required(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        response = authenticated_client.post(
            f"/metrics/{tuning_metric.id}/tuning/cases",
            json={"output": CASE_OUTPUT},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_output_is_required(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        """The metric judges an answer, so there has to be an answer."""
        response = authenticated_client.post(
            f"/metrics/{tuning_metric.id}/tuning/cases",
            json={"input": CASE_INPUT},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_unknown_metric_404s(self, authenticated_client: TestClient):
        response = authenticated_client.post(
            f"/metrics/{uuid.uuid4()}/tuning/cases",
            json={"input": CASE_INPUT, "output": CASE_OUTPUT},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
class TestACaseNobodyHasRun:
    """A case can be captured now and judged after a run."""

    def test_it_reads_as_unreviewed_because_it_was_never_judged(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        """Unreviewed is never accepted, and a case with no verdict yet says why."""
        created = _create_case(authenticated_client, tuning_metric.id)

        assert created["outcome"] == "unreviewed"
        assert created["unreviewed_reason"] == "never_judged"
        assert created["review"] is None
        assert created["result"] is None

    def test_it_is_listed_like_any_other_case(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        """It is a complete case -- the metric could be run over it."""
        created = _create_case(authenticated_client, tuning_metric.id)

        listed = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/cases").json()

        assert [item["id"] for item in listed] == [created["id"]]
        assert listed[0]["outcome"] == "unreviewed"
        assert listed[0]["input"] == CASE_INPUT
        assert listed[0]["output"] == CASE_OUTPUT


@pytest.mark.integration
class TestUpdateTuningCase:
    """PUT /metrics/{metric_id}/tuning/cases/{case_id}"""

    def test_updates_every_field(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        created = _create_case(authenticated_client, tuning_metric.id)

        response = authenticated_client.put(
            f"/metrics/{tuning_metric.id}/tuning/cases/{created['id']}",
            json={
                "input": "Are you well?",
                "output": "Yes, thanks.",
                "reference_answer": "Yes, thank you for asking.",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["input"] == "Are you well?"
        assert data["output"] == "Yes, thanks."
        assert data["reference_answer"] == "Yes, thank you for asking."

    def test_omitted_fields_are_left_alone(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        created = _create_case(authenticated_client, tuning_metric.id)

        response = authenticated_client.put(
            f"/metrics/{tuning_metric.id}/tuning/cases/{created['id']}",
            json={"output": "Yes, thanks."},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["output"] == "Yes, thanks."
        assert data["input"] == CASE_INPUT
        assert data["reference_answer"] == CASE_REFERENCE_ANSWER

    def test_editing_a_case_leaves_its_reviews_alone(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        """Editing a case is not judging it. A review that no longer fits is
        invalidated by the material-change rule on the next run, not wiped here."""
        created = _create_case(authenticated_client, tuning_metric.id)
        db_test = _load_case(test_db, created["id"])
        db_test.test_metadata = {
            "result": {"verdict": "pass", "reasoning": "reads as polite"},
            "reviews": [
                {
                    "decision": "rejected",
                    "comment": "scored a pass, but this is an insult",
                    "verdict": "pass",
                    "score_type": "binary",
                }
            ],
        }
        test_db.commit()

        response = authenticated_client.put(
            f"/metrics/{tuning_metric.id}/tuning/cases/{created['id']}",
            json={"output": "I am fine, you idiot"},
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["review"]["comment"] == "scored a pass, but this is an insult"
        test_db.refresh(db_test)
        assert db_test.test_metadata["reviews"] == [
            {
                "decision": "rejected",
                "comment": "scored a pass, but this is an insult",
                "verdict": "pass",
                "score_type": "binary",
            }
        ]

    def test_case_from_another_metric_404s(
        self,
        authenticated_client: TestClient,
        tuning_metric: models.Metric,
        other_metric: models.Metric,
    ):
        """The membership join is the authorization check."""
        theirs = _create_case(authenticated_client, other_metric.id)

        response = authenticated_client.put(
            f"/metrics/{tuning_metric.id}/tuning/cases/{theirs['id']}",
            json={"output": "Yes, thanks."},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unknown_case_404s(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        _create_case(authenticated_client, tuning_metric.id)

        response = authenticated_client.put(
            f"/metrics/{tuning_metric.id}/tuning/cases/{uuid.uuid4()}",
            json={"output": "Yes, thanks."},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
class TestCasesStoredBeforeTheRename:
    """`expected_output` was renamed `reference_answer`."""

    def test_the_old_key_still_reads_as_the_reference_answer(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        """Dropping the text on a rename would silently edit the thing being scored."""
        created = _create_case(authenticated_client, tuning_metric.id)
        db_test = _load_case(test_db, created["id"])
        db_test.prompt.content = json.dumps(
            {
                "input": CASE_INPUT,
                "output": CASE_OUTPUT,
                "expected_output": CASE_REFERENCE_ANSWER,
            }
        )
        test_db.commit()

        listed = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/cases").json()

        assert [item["reference_answer"] for item in listed] == [CASE_REFERENCE_ANSWER]

    def test_editing_such_a_case_rewrites_it_under_the_new_key(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        created = _create_case(authenticated_client, tuning_metric.id)
        db_test = _load_case(test_db, created["id"])
        db_test.prompt.content = json.dumps(
            {
                "input": CASE_INPUT,
                "output": CASE_OUTPUT,
                "expected_output": CASE_REFERENCE_ANSWER,
            }
        )
        test_db.commit()

        response = authenticated_client.put(
            f"/metrics/{tuning_metric.id}/tuning/cases/{created['id']}",
            json={"output": "Yes, thanks."},
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        test_db.refresh(db_test.prompt)
        payload = json.loads(db_test.prompt.content)
        assert payload == {
            "input": CASE_INPUT,
            "output": "Yes, thanks.",
            "reference_answer": CASE_REFERENCE_ANSWER,
        }


@pytest.mark.integration
class TestDeleteTuningCase:
    """DELETE /metrics/{metric_id}/tuning/cases/{case_id}"""

    def test_removes_the_case_from_the_list(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        created = _create_case(authenticated_client, tuning_metric.id)

        response = authenticated_client.delete(
            f"/metrics/{tuning_metric.id}/tuning/cases/{created['id']}"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["deleted"] is True

        remaining = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/cases").json()
        assert created["id"] not in {item["id"] for item in remaining}

    def test_case_from_another_metric_404s(
        self,
        authenticated_client: TestClient,
        tuning_metric: models.Metric,
        other_metric: models.Metric,
    ):
        theirs = _create_case(authenticated_client, other_metric.id)

        response = authenticated_client.delete(
            f"/metrics/{tuning_metric.id}/tuning/cases/{theirs['id']}"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

        still_there = authenticated_client.get(f"/metrics/{other_metric.id}/tuning/cases").json()
        assert theirs["id"] in {item["id"] for item in still_there}


@pytest.mark.integration
class TestTuningRowsAreUnreachable:
    """Metric-owned rows are reachable only through their metric.

    Hiding them from the lists is not enough on its own: the identifier would
    still be a working handle to data the feature promises is private.
    """

    def test_tuning_test_set_absent_from_test_sets_list(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        _create_case(authenticated_client, tuning_metric.id)
        test_set = (
            test_db.query(models.TestSet).filter(models.TestSet.metric_id == tuning_metric.id).one()
        )

        response = authenticated_client.get("/test_sets/?limit=100")

        assert response.status_code == status.HTTP_200_OK
        assert str(test_set.id) not in {item["id"] for item in response.json()}

    def test_tuning_test_set_not_reachable_by_id(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        _create_case(authenticated_client, tuning_metric.id)
        test_set = (
            test_db.query(models.TestSet).filter(models.TestSet.metric_id == tuning_metric.id).one()
        )

        response = authenticated_client.get(f"/test_sets/{test_set.id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_tuning_case_absent_from_tests_list(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        created = _create_case(authenticated_client, tuning_metric.id)

        response = authenticated_client.get("/tests/?limit=100")

        assert response.status_code == status.HTTP_200_OK
        assert created["id"] not in {item["id"] for item in response.json()}

    def test_tuning_case_not_reachable_by_id(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        created = _create_case(authenticated_client, tuning_metric.id)

        response = authenticated_client.get(f"/tests/{created['id']}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_tests_count_header_matches_returned_rows(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        """A hidden row counted but not listed would produce a phantom page."""
        before = authenticated_client.get("/tests/?limit=100")
        before_count = int(before.headers["X-Total-Count"])

        _create_case(authenticated_client, tuning_metric.id)

        after = authenticated_client.get("/tests/?limit=100")
        assert int(after.headers["X-Total-Count"]) == before_count
        assert len(after.json()) == len(before.json())
