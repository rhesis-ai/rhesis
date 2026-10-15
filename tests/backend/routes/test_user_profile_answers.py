"""Job role and referral source, asked in onboarding (creators) or a one-time dialog (invitees)."""

from unittest.mock import patch

import pytest
from fastapi import status
from pydantic import ValidationError

from rhesis.backend.app import models
from rhesis.backend.app.schemas.user import UserUpdate
from rhesis.backend.app.services.onboarding import mark_profile_survey_pending


@pytest.mark.unit
class TestProfileAnswerSchema:
    def test_accepts_known_keys(self):
        update = UserUpdate(job_role="data_scientist", referral_source="ai_assistant")

        assert update.job_role == "data_scientist"
        assert update.referral_source == "ai_assistant"

    @pytest.mark.parametrize("field", ["job_role", "referral_source"])
    def test_rejects_unknown_keys(self, field):
        with pytest.raises(ValidationError):
            UserUpdate(**{field: "astronaut"})

    def test_rejects_overlong_other_text(self):
        with pytest.raises(ValidationError):
            UserUpdate(job_role="other", job_role_other="x" * 256)


@pytest.mark.unit
class TestMarkProfileSurveyPending:
    def test_sets_flag_for_user_without_answers(self):
        user = models.User(email="invitee@example.com", user_settings={"version": 1})

        mark_profile_survey_pending(user)

        assert user.user_settings["onboarding"]["profile_survey_pending"] is True

    def test_skips_user_who_already_answered(self):
        user = models.User(email="rejoin@example.com", user_settings={"version": 1}, job_role="qa")

        mark_profile_survey_pending(user)

        assert "onboarding" not in user.user_settings


class TestProfileAnswerRoutes:
    def test_invite_marks_survey_pending(self, authenticated_client, test_db):
        with patch(
            "rhesis.backend.app.routers.user.validate_and_normalize_email",
            side_effect=lambda email, check_deliverability=False: email,
        ):
            response = authenticated_client.post(
                "/users/", json={"email": "survey-invitee@example.com"}
            )

        assert response.status_code == status.HTTP_200_OK
        # Read back from the DB: the response is built from the in-memory row
        test_db.expire_all()
        invitee = test_db.query(models.User).filter_by(id=response.json()["id"]).one()
        assert invitee.user_settings["onboarding"]["profile_survey_pending"] is True

    def test_self_update_stores_answers(self, authenticated_client, authenticated_user_id):
        response = authenticated_client.put(
            f"/users/{authenticated_user_id}",
            json={
                "job_role": "other",
                "job_role_other": "Prompt engineer",
                "referral_source": "github",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        user = response.json()["user"]
        assert user["job_role"] == "other"
        assert user["job_role_other"] == "Prompt engineer"
        assert user["referral_source"] == "github"
        assert user["referral_source_other"] is None

    def test_clearing_the_flag_via_settings(self, authenticated_client):
        response = authenticated_client.patch(
            "/users/settings", json={"onboarding": {"profile_survey_pending": False}}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["onboarding"]["profile_survey_pending"] is False
