"""
Integration tests for metric tuning route endpoints.

Tests the HTTP endpoints:
- GET    /metrics/{metric_id}/tuning/cases
- POST   /metrics/{metric_id}/tuning/cases
- PUT    /metrics/{metric_id}/tuning/cases/{case_id}
- DELETE /metrics/{metric_id}/tuning/cases/{case_id}

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
CASE_EXPECTED_OUTPUT = "I am fine, thanks for asking."
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
def numeric_metric(test_db: Session, test_org_id, authenticated_user_id) -> models.Metric:
    metric = _make_metric(
        test_db,
        f"Numeric Metric {uuid.uuid4().hex[:6]}",
        test_org_id,
        authenticated_user_id,
        score_type="numeric",
        min_score=0.0,
        max_score=1.0,
        threshold=0.5,
    )
    return _persist(test_db, metric)


@pytest.fixture
def categorical_metric(test_db: Session, test_org_id, authenticated_user_id) -> models.Metric:
    metric = _make_metric(
        test_db,
        f"Categorical Metric {uuid.uuid4().hex[:6]}",
        test_org_id,
        authenticated_user_id,
        score_type="categorical",
        categories=["safe", "borderline", "toxic"],
        passing_categories=["safe"],
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
        "expected_output": CASE_EXPECTED_OUTPUT,
        "expected": CASE_EXPECTED,
        "rationale": CASE_RATIONALE,
    }
    body.update(overrides)
    response = client.post(f"/metrics/{metric_id}/tuning/cases", json=body)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


@pytest.mark.integration
@pytest.mark.routes
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
@pytest.mark.routes
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
            json={"input": CASE_INPUT, "output": CASE_OUTPUT, "expected": CASE_EXPECTED},
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
            json={"input": CASE_INPUT, "output": CASE_OUTPUT, "expected": CASE_EXPECTED},
        )

        assert (
            test_db.query(models.TestSet)
            .filter(models.TestSet.metric_id == framework_metric.id)
            .first()
            is None
        )


@pytest.mark.integration
@pytest.mark.routes
class TestCreateTuningCase:
    """POST /metrics/{metric_id}/tuning/cases"""

    def test_returns_the_case_it_stored(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        data = _create_case(authenticated_client, tuning_metric.id)

        assert data["input"] == CASE_INPUT
        assert data["output"] == CASE_OUTPUT
        assert data["expected"] == CASE_EXPECTED
        assert data["rationale"] == CASE_RATIONALE
        assert data["is_stale"] is False

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

        Comparing a verdict against the expected one is plain code, not a metric
        (ADR-0004), so nothing is waiting to be attached here. The placeholder
        that used to hold the slot open was a metric row that computed nothing
        and showed up in the organization's metric library."""
        _create_case(authenticated_client, tuning_metric.id)

        test_set = (
            test_db.query(models.TestSet)
            .options(joinedload(models.TestSet.metrics))
            .filter(models.TestSet.metric_id == tuning_metric.id)
            .one()
        )
        assert list(test_set.metrics) == []

    def test_returns_the_expected_output_it_stored(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        """The answer the system under test should have given, for metrics that
        judge against a reference."""
        data = _create_case(authenticated_client, tuning_metric.id)

        assert data["expected_output"] == CASE_EXPECTED_OUTPUT

    def test_expected_output_is_optional(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        """Plenty of metrics judge an answer without a reference to compare to."""
        response = authenticated_client.post(
            f"/metrics/{tuning_metric.id}/tuning/cases",
            json={"input": CASE_INPUT, "output": CASE_OUTPUT, "expected": CASE_EXPECTED},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["expected_output"] is None

    def test_stores_the_whole_case_payload_in_prompt_content(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        """prompt.content is what the system under test receives, and here the
        system under test is the metric -- so it gets the whole case."""
        data = _create_case(authenticated_client, tuning_metric.id)

        db_test = (
            test_db.query(models.Test)
            .options(joinedload(models.Test.prompt))
            .filter(models.Test.id == data["id"])
            .one()
        )
        payload = json.loads(db_test.prompt.content)
        assert payload["input"] == CASE_INPUT
        assert payload["output"] == CASE_OUTPUT
        assert payload["expected_output"] == CASE_EXPECTED_OUTPUT

    def test_the_verdict_is_not_part_of_the_payload(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        """The verdict is the answer key. Putting it in the payload would show
        the metric what it is supposed to say."""
        data = _create_case(authenticated_client, tuning_metric.id)

        db_test = (
            test_db.query(models.Test)
            .options(joinedload(models.Test.prompt))
            .filter(models.Test.id == data["id"])
            .one()
        )
        assert "expected" not in json.loads(db_test.prompt.content)
        assert db_test.prompt.expected_response == CASE_EXPECTED

    def test_metadata_holds_only_the_rationale(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        """The output moved into the payload; the rationale is not shown to the
        metric, so it stays out of it."""
        data = _create_case(authenticated_client, tuning_metric.id)

        db_test = test_db.query(models.Test).filter(models.Test.id == data["id"]).one()
        assert db_test.test_metadata.get("rationale") == CASE_RATIONALE
        assert "output" not in db_test.test_metadata

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

    def test_rationale_is_optional(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        """The reasoning is for the reviewer, not for scoring."""
        response = authenticated_client.post(
            f"/metrics/{tuning_metric.id}/tuning/cases",
            json={"input": CASE_INPUT, "output": CASE_OUTPUT, "expected": CASE_EXPECTED},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["rationale"] is None

    def test_input_is_required(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        response = authenticated_client.post(
            f"/metrics/{tuning_metric.id}/tuning/cases",
            json={"output": CASE_OUTPUT, "expected": CASE_EXPECTED},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_output_is_required(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        """The metric judges an answer, so there has to be an answer."""
        response = authenticated_client.post(
            f"/metrics/{tuning_metric.id}/tuning/cases",
            json={"input": CASE_INPUT, "expected": CASE_EXPECTED},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_unknown_metric_404s(self, authenticated_client: TestClient):
        response = authenticated_client.post(
            f"/metrics/{uuid.uuid4()}/tuning/cases",
            json={"input": CASE_INPUT, "output": CASE_OUTPUT, "expected": CASE_EXPECTED},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
@pytest.mark.routes
class TestUnlabelledCases:
    """A case can be captured now and judged later."""

    def test_a_case_saves_without_a_verdict(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        response = authenticated_client.post(
            f"/metrics/{tuning_metric.id}/tuning/cases",
            json={"input": CASE_INPUT, "output": CASE_OUTPUT},
        )

        assert response.status_code == status.HTTP_201_CREATED, response.text
        assert response.json()["expected"] is None

    def test_a_blank_verdict_is_the_same_as_none(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        """An empty verdict control must not be stored as an empty verdict."""
        response = authenticated_client.post(
            f"/metrics/{tuning_metric.id}/tuning/cases",
            json={"input": CASE_INPUT, "output": CASE_OUTPUT, "expected": "   "},
        )

        assert response.status_code == status.HTTP_201_CREATED, response.text
        assert response.json()["expected"] is None

    def test_an_unlabelled_case_is_listed(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        """It is a complete case -- the metric could be run over it."""
        created = _create_case(authenticated_client, tuning_metric.id, expected=None)

        listed = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/cases").json()

        assert [item["id"] for item in listed] == [created["id"]]
        assert listed[0]["expected"] is None
        assert listed[0]["input"] == CASE_INPUT
        assert listed[0]["output"] == CASE_OUTPUT

    def test_an_unlabelled_case_is_not_stale(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        """Staleness is about a verdict that no longer fits, not an absent one."""
        _create_case(authenticated_client, tuning_metric.id, expected=None)

        tuning_metric.score_type = "numeric"
        tuning_metric.min_score = 0.0
        tuning_metric.max_score = 1.0
        test_db.commit()

        listed = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/cases").json()

        assert [item["is_stale"] for item in listed] == [False]

    def test_a_verdict_supplied_later_is_stored(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        created = _create_case(authenticated_client, tuning_metric.id, expected=None)

        response = authenticated_client.put(
            f"/metrics/{tuning_metric.id}/tuning/cases/{created['id']}",
            json={"expected": "pass"},
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["expected"] == "pass"

    def test_a_verdict_supplied_later_is_validated(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        """Judging late is not judging loosely -- the same check runs as on create."""
        created = _create_case(authenticated_client, tuning_metric.id, expected=None)

        response = authenticated_client.put(
            f"/metrics/{tuning_metric.id}/tuning/cases/{created['id']}",
            json={"expected": "maybe"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "binary" in response.json()["detail"]

    def test_a_verdict_can_be_taken_back(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        """A blank verdict on update returns the case to unlabelled."""
        created = _create_case(authenticated_client, tuning_metric.id)

        response = authenticated_client.put(
            f"/metrics/{tuning_metric.id}/tuning/cases/{created['id']}",
            json={"expected": ""},
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["expected"] is None

    def test_an_omitted_verdict_leaves_an_existing_one_alone(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        """Absent and blank differ on update: omitted means "do not touch"."""
        created = _create_case(authenticated_client, tuning_metric.id)

        response = authenticated_client.put(
            f"/metrics/{tuning_metric.id}/tuning/cases/{created['id']}",
            json={"rationale": "still toxic"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["expected"] == CASE_EXPECTED


@pytest.mark.integration
@pytest.mark.routes
class TestExpectedVerdictIsValidated:
    """The verdict is one string for all score types, so it is checked against
    the metric that owns it."""

    def test_binary_rejects_anything_but_pass_or_fail(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        response = authenticated_client.post(
            f"/metrics/{tuning_metric.id}/tuning/cases",
            json={"input": CASE_INPUT, "output": CASE_OUTPUT, "expected": "yes"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "binary" in response.json()["detail"].lower()

    def test_binary_verdict_is_stored_lowercase(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        """So "Pass" and "pass" cannot both live in one tuning test set."""
        data = _create_case(authenticated_client, tuning_metric.id, expected="Pass")

        assert data["expected"] == "pass"

    def test_numeric_rejects_a_non_number(
        self, authenticated_client: TestClient, numeric_metric: models.Metric
    ):
        response = authenticated_client.post(
            f"/metrics/{numeric_metric.id}/tuning/cases",
            json={"input": CASE_INPUT, "output": CASE_OUTPUT, "expected": "fail"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_numeric_rejects_a_value_outside_the_range(
        self, authenticated_client: TestClient, numeric_metric: models.Metric
    ):
        response = authenticated_client.post(
            f"/metrics/{numeric_metric.id}/tuning/cases",
            json={"input": CASE_INPUT, "output": CASE_OUTPUT, "expected": "1.5"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_numeric_accepts_a_value_in_range(
        self, authenticated_client: TestClient, numeric_metric: models.Metric
    ):
        data = _create_case(authenticated_client, numeric_metric.id, expected="0.8")

        assert data["expected"] == "0.8"
        assert data["is_stale"] is False

    def test_categorical_rejects_an_unknown_category(
        self, authenticated_client: TestClient, categorical_metric: models.Metric
    ):
        response = authenticated_client.post(
            f"/metrics/{categorical_metric.id}/tuning/cases",
            json={"input": CASE_INPUT, "output": CASE_OUTPUT, "expected": "spicy"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_categorical_accepts_one_of_the_metrics_categories(
        self, authenticated_client: TestClient, categorical_metric: models.Metric
    ):
        data = _create_case(authenticated_client, categorical_metric.id, expected="toxic")

        assert data["expected"] == "toxic"

    def test_update_validates_the_new_verdict(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        created = _create_case(authenticated_client, tuning_metric.id)

        response = authenticated_client.put(
            f"/metrics/{tuning_metric.id}/tuning/cases/{created['id']}",
            json={"expected": "maybe"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.integration
@pytest.mark.routes
class TestStaleCases:
    """A verdict that no longer fits its metric is marked, not deleted."""

    def test_case_becomes_stale_when_the_score_type_changes(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        created = _create_case(authenticated_client, tuning_metric.id)
        assert created["is_stale"] is False

        # The metric author switches the metric from binary to numeric; "fail"
        # is no longer something this metric can return.
        tuning_metric.score_type = "numeric"
        tuning_metric.min_score = 0.0
        tuning_metric.max_score = 1.0
        test_db.commit()

        listed = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/cases").json()

        assert [item["is_stale"] for item in listed] == [True]

    def test_stale_cases_are_kept(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        """Work typed by hand is never destroyed on the author's behalf."""
        created = _create_case(authenticated_client, tuning_metric.id)

        tuning_metric.score_type = "numeric"
        test_db.commit()

        listed = authenticated_client.get(f"/metrics/{tuning_metric.id}/tuning/cases").json()

        assert [item["id"] for item in listed] == [created["id"]]

    def test_a_stale_case_can_still_be_fixed(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        tuning_metric: models.Metric,
    ):
        """Editing a stale case must be possible, or it could never be repaired."""
        created = _create_case(authenticated_client, tuning_metric.id)

        tuning_metric.score_type = "numeric"
        tuning_metric.min_score = 0.0
        tuning_metric.max_score = 1.0
        test_db.commit()

        response = authenticated_client.put(
            f"/metrics/{tuning_metric.id}/tuning/cases/{created['id']}",
            json={"expected": "0.2"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_stale"] is False


@pytest.mark.integration
@pytest.mark.routes
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
                "expected": "pass",
                "rationale": "not toxic",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["input"] == "Are you well?"
        assert data["output"] == "Yes, thanks."
        assert data["expected"] == "pass"
        assert data["rationale"] == "not toxic"

    def test_omitted_fields_are_left_alone(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        created = _create_case(authenticated_client, tuning_metric.id)

        response = authenticated_client.put(
            f"/metrics/{tuning_metric.id}/tuning/cases/{created['id']}",
            json={"expected": "pass"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["expected"] == "pass"
        assert data["input"] == CASE_INPUT
        assert data["output"] == CASE_OUTPUT
        assert data["rationale"] == CASE_RATIONALE

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
            json={"expected": "pass"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unknown_case_404s(
        self, authenticated_client: TestClient, tuning_metric: models.Metric
    ):
        _create_case(authenticated_client, tuning_metric.id)

        response = authenticated_client.put(
            f"/metrics/{tuning_metric.id}/tuning/cases/{uuid.uuid4()}",
            json={"expected": "pass"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
@pytest.mark.routes
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
@pytest.mark.routes
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
