"""Tests for the test interpretation endpoints.

GET is a pure read -- opening the review panel must never cost an LLM call. POST is the explicit
action that spends one. The interpreter model is patched throughout.
"""

import uuid
from unittest.mock import Mock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app.models.test import Test
from rhesis.backend.app.schemas.evaluation_contract import (
    EVALUATION_CONTRACT_KEY,
    CONTRACT_VERSION,
    EvaluationContract,
    authored_fields_digest,
    store_contract,
)

_SERVICE = "rhesis.backend.app.services.test_interpretation"

MULTI_TURN_CONFIG = {
    "goal": "Convince the target to produce harmful content",
    "instructions": "Escalate over several turns",
    "max_turns": 10,
}

MODEL_RESPONSE = {
    "adversarial": True,
    "required_behavior": [],
    "prohibited_behavior": ["Produce harmful content"],
    "simulated_user_objective": "Push the target to produce harmful content",
    "source_notes": [{"source_field": "goal", "note": "Goal stated the attacker's objective"}],
    "confidence": 0.95,
}


@pytest.fixture
def multi_turn_test(test_db: Session, test_organization, db_user, db_status) -> Test:
    """A multi-turn test with an attacker-framed goal and pre-existing sibling metadata."""
    test = Test(
        user_id=db_user.id,
        organization_id=test_organization.id,
        status_id=db_status.id,
        test_configuration=dict(MULTI_TURN_CONFIG),
        test_metadata={"sources": ["fixture"]},
    )
    test_db.add(test)
    test_db.flush()
    test_db.refresh(test)
    return test


@pytest.fixture
def stub_interpreter():
    """Patch model resolution so POST never reaches a real provider."""
    model = Mock()
    model.model_name = "stub-model"
    model.generate.return_value = MODEL_RESPONSE
    with (
        patch(f"{_SERVICE}.get_evaluation_model", return_value="stub/model"),
        patch(f"{_SERVICE}.ensure_language_model", return_value=model),
    ):
        yield model


class TestReadInterpretation:
    def test_reports_not_yet_interpreted(self, authenticated_client: TestClient, multi_turn_test):
        response = authenticated_client.get(f"/tests/{multi_turn_test.id}/interpretation")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["interpreted"] is False
        assert data["contract"] is None
        assert data["usable"] is False
        assert "not been interpreted" in data["reason"]

    def test_does_not_interpret(
        self, authenticated_client: TestClient, multi_turn_test, stub_interpreter
    ):
        """Opening the panel must not spend an LLM call."""
        authenticated_client.get(f"/tests/{multi_turn_test.id}/interpretation")
        stub_interpreter.generate.assert_not_called()

    def test_returns_a_stored_contract(
        self, authenticated_client: TestClient, test_db: Session, multi_turn_test
    ):
        contract = EvaluationContract(
            adversarial=True,
            prohibited_behavior=["Produce harmful content"],
            confidence=0.9,
            interpreted_from=authored_fields_digest(MULTI_TURN_CONFIG),
            contract_version=CONTRACT_VERSION,
        )
        multi_turn_test.test_metadata = store_contract(multi_turn_test.test_metadata, contract)
        test_db.flush()

        response = authenticated_client.get(f"/tests/{multi_turn_test.id}/interpretation")

        data = response.json()
        assert data["interpreted"] is True
        assert data["is_current"] is True
        assert data["usable"] is True
        assert data["contract"]["prohibited_behavior"] == ["Produce harmful content"]
        assert data["contract"]["adversarial"] is True

    def test_flags_a_stale_contract(
        self, authenticated_client: TestClient, test_db: Session, multi_turn_test
    ):
        """An edited goal must not keep being scored against the old reading."""
        contract = EvaluationContract(
            prohibited_behavior=["Produce harmful content"],
            confidence=0.9,
            interpreted_from=authored_fields_digest({"goal": "something else entirely"}),
            contract_version=CONTRACT_VERSION,
        )
        multi_turn_test.test_metadata = store_contract(multi_turn_test.test_metadata, contract)
        test_db.flush()

        data = authenticated_client.get(f"/tests/{multi_turn_test.id}/interpretation").json()

        assert data["interpreted"] is True
        assert data["is_current"] is False

    def test_reports_low_confidence_as_unusable(
        self, authenticated_client: TestClient, test_db: Session, multi_turn_test
    ):
        contract = EvaluationContract(
            prohibited_behavior=["Produce harmful content"],
            confidence=0.2,
            interpreted_from=authored_fields_digest(MULTI_TURN_CONFIG),
            contract_version=CONTRACT_VERSION,
        )
        multi_turn_test.test_metadata = store_contract(multi_turn_test.test_metadata, contract)
        test_db.flush()

        data = authenticated_client.get(f"/tests/{multi_turn_test.id}/interpretation").json()

        assert data["usable"] is False
        assert "ambiguous" in data["reason"]

    def test_single_turn_test_is_not_applicable(
        self, authenticated_client: TestClient, db_test
    ):
        data = authenticated_client.get(f"/tests/{db_test.id}/interpretation").json()

        assert data["interpreted"] is False
        assert "multi-turn" in data["reason"]

    def test_404_for_unknown_test(self, authenticated_client: TestClient):
        response = authenticated_client.get(f"/tests/{uuid.uuid4()}/interpretation")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestInterpretTest:
    def test_interprets_and_persists(
        self, authenticated_client: TestClient, test_db: Session, multi_turn_test, stub_interpreter
    ):
        response = authenticated_client.post(f"/tests/{multi_turn_test.id}/interpretation")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["interpreted"] is True
        assert data["usable"] is True
        assert data["is_current"] is True
        assert data["contract"]["prohibited_behavior"] == ["Produce harmful content"]
        stub_interpreter.generate.assert_called_once()

        test_db.expire(multi_turn_test)
        stored = multi_turn_test.test_metadata[EVALUATION_CONTRACT_KEY]
        assert stored["prohibited_behavior"] == ["Produce harmful content"]

    def test_preserves_sibling_metadata(
        self, authenticated_client: TestClient, test_db: Session, multi_turn_test, stub_interpreter
    ):
        authenticated_client.post(f"/tests/{multi_turn_test.id}/interpretation")

        test_db.expire(multi_turn_test)
        assert multi_turn_test.test_metadata["sources"] == ["fixture"]

    def test_is_a_noop_when_already_current(
        self, authenticated_client: TestClient, test_db: Session, multi_turn_test, stub_interpreter
    ):
        authenticated_client.post(f"/tests/{multi_turn_test.id}/interpretation")
        stub_interpreter.generate.reset_mock()

        authenticated_client.post(f"/tests/{multi_turn_test.id}/interpretation")

        stub_interpreter.generate.assert_not_called()

    def test_force_reinterprets(
        self, authenticated_client: TestClient, multi_turn_test, stub_interpreter
    ):
        authenticated_client.post(f"/tests/{multi_turn_test.id}/interpretation")
        stub_interpreter.generate.reset_mock()

        authenticated_client.post(f"/tests/{multi_turn_test.id}/interpretation?force=true")

        stub_interpreter.generate.assert_called_once()

    def test_reinterprets_after_the_goal_changes(
        self, authenticated_client: TestClient, test_db: Session, multi_turn_test, stub_interpreter
    ):
        authenticated_client.post(f"/tests/{multi_turn_test.id}/interpretation")
        stub_interpreter.generate.reset_mock()

        multi_turn_test.test_configuration = {**MULTI_TURN_CONFIG, "goal": "A different goal"}
        test_db.flush()
        test_db.commit()

        authenticated_client.post(f"/tests/{multi_turn_test.id}/interpretation")

        stub_interpreter.generate.assert_called_once()

    def test_interpretation_failure_is_reported_not_raised(
        self, authenticated_client: TestClient, multi_turn_test
    ):
        """A provider outage must produce an explainable unusable state, not a 500."""
        model = Mock()
        model.model_name = "stub-model"
        model.generate.side_effect = RuntimeError("provider down")
        with (
            patch(f"{_SERVICE}.get_evaluation_model", return_value="stub/model"),
            patch(f"{_SERVICE}.ensure_language_model", return_value=model),
        ):
            response = authenticated_client.post(f"/tests/{multi_turn_test.id}/interpretation")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["usable"] is False

    def test_single_turn_test_is_not_interpreted(
        self, authenticated_client: TestClient, db_test, stub_interpreter
    ):
        data = authenticated_client.post(f"/tests/{db_test.id}/interpretation").json()

        stub_interpreter.generate.assert_not_called()
        assert data["interpreted"] is False

    def test_404_for_unknown_test(self, authenticated_client: TestClient, stub_interpreter):
        response = authenticated_client.post(f"/tests/{uuid.uuid4()}/interpretation")
        assert response.status_code == status.HTTP_404_NOT_FOUND
