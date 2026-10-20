"""Job role and referral source, asked in onboarding (creators) or a one-time dialog (invitees).

Stored in ``user_settings.onboarding.profile``."""

from unittest.mock import patch

import pytest
from fastapi import status
from pydantic import ValidationError

from rhesis.backend.app import models
from rhesis.backend.app.schemas.user import OnboardingProfile
from rhesis.backend.app.services.onboarding import mark_profile_survey_pending


def _invite(client, email: str):
    with patch(
        "rhesis.backend.app.routers.user.validate_and_normalize_email",
        side_effect=lambda email, check_deliverability=False: email,
    ):
        return client.post("/users/", json={"email": email})


@pytest.mark.unit
class TestProfileAnswerSchema:
    def test_accepts_known_keys(self):
        profile = OnboardingProfile(job_role="data_scientist", referral_source="ai_assistant")

        assert profile.job_role == "data_scientist"
        assert profile.referral_source == "ai_assistant"

    @pytest.mark.parametrize("field", ["job_role", "referral_source"])
    def test_rejects_unknown_keys(self, field):
        with pytest.raises(ValidationError):
            OnboardingProfile(**{field: "astronaut"})

    def test_rejects_overlong_other_text(self):
        with pytest.raises(ValidationError):
            OnboardingProfile(job_role="other", job_role_other="x" * 256)


@pytest.mark.unit
class TestMarkProfileSurveyPending:
    def test_sets_flag_for_user_without_answers(self):
        user = models.User(email="invitee@example.com", user_settings={"version": 1})

        mark_profile_survey_pending(user)

        assert user.user_settings["onboarding"]["profile_survey_pending"] is True

    def test_skips_user_who_already_answered(self):
        user = models.User(
            email="answered@example.com",
            user_settings={"version": 1, "onboarding": {"profile": {"job_role": "qa"}}},
        )

        mark_profile_survey_pending(user)

        assert "profile_survey_pending" not in user.user_settings["onboarding"]


class TestProfileAnswerRoutes:
    def test_invite_marks_survey_pending(self, authenticated_client, test_db):
        response = _invite(authenticated_client, "survey-invitee@example.com")

        assert response.status_code == status.HTTP_200_OK
        # Read back from the DB: the response is built from the in-memory row
        test_db.expire_all()
        invitee = test_db.query(models.User).filter_by(id=response.json()["id"]).one()
        assert invitee.user_settings["onboarding"]["profile_survey_pending"] is True

    def test_reinvite_does_not_mark_survey_pending(self, authenticated_client, test_db):
        test_db.add(models.User(email="rejoin@example.com", user_settings={"version": 1}))
        test_db.flush()

        response = _invite(authenticated_client, "rejoin@example.com")

        assert response.status_code == status.HTTP_200_OK
        test_db.expire_all()
        rejoined = test_db.query(models.User).filter_by(id=response.json()["id"]).one()
        assert "onboarding" not in rejoined.user_settings

    def test_reinvite_hides_earlier_answers_from_inviter(self, authenticated_client, test_db):
        test_db.add(
            models.User(
                email="rejoin-answered@example.com",
                user_settings={"version": 1, "onboarding": {"profile": {"job_role": "qa"}}},
            )
        )
        test_db.flush()

        response = _invite(authenticated_client, "rejoin-answered@example.com")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["user_settings"]["onboarding"]["profile"] is None

    def test_saving_answers_clears_the_flag(self, authenticated_client):
        response = authenticated_client.patch(
            "/users/settings",
            json={
                "onboarding": {
                    "profile_survey_pending": False,
                    "profile": {
                        "job_role": "other",
                        "job_role_other": "Prompt engineer",
                        "referral_source": "github",
                        "referral_source_other": None,
                    },
                }
            },
        )

        assert response.status_code == status.HTTP_200_OK
        onboarding = response.json()["onboarding"]
        assert onboarding["profile_survey_pending"] is False
        assert onboarding["profile"] == {
            "job_role": "other",
            "job_role_other": "Prompt engineer",
            "referral_source": "github",
            "referral_source_other": None,
        }

    def test_switching_away_from_other_clears_its_text(self, authenticated_client):
        authenticated_client.patch(
            "/users/settings",
            json={"onboarding": {"profile": {"job_role": "other", "job_role_other": "Founder"}}},
        )

        response = authenticated_client.patch(
            "/users/settings",
            json={"onboarding": {"profile": {"job_role": "engineer", "job_role_other": None}}},
        )

        assert response.status_code == status.HTTP_200_OK
        profile = response.json()["onboarding"]["profile"]
        assert profile["job_role"] == "engineer"
        assert profile["job_role_other"] is None

    def test_rejects_unknown_role(self, authenticated_client):
        response = authenticated_client.patch(
            "/users/settings", json={"onboarding": {"profile": {"job_role": "astronaut"}}}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestProfileAnswerVisibility:
    PROFILE = {"job_role": "qa", "referral_source": "github"}

    @pytest.fixture
    def teammate_id(self, authenticated_client, test_db):
        response = _invite(authenticated_client, "survey-teammate@example.com")
        teammate = test_db.query(models.User).filter_by(id=response.json()["id"]).one()
        teammate.user_settings = {"version": 1, "onboarding": {"profile": self.PROFILE}}
        test_db.flush()
        return str(teammate.id)

    def test_list_hides_other_members_answers(
        self, authenticated_client, authenticated_user_id, teammate_id
    ):
        authenticated_client.patch(
            "/users/settings", json={"onboarding": {"profile": self.PROFILE}}
        )

        response = authenticated_client.get("/users/", params={"limit": 100})

        assert response.status_code == status.HTTP_200_OK
        users = {u["id"]: u for u in response.json()}
        assert users[teammate_id]["user_settings"]["onboarding"]["profile"] is None
        own_profile = users[authenticated_user_id]["user_settings"]["onboarding"]["profile"]
        assert own_profile["job_role"] == "qa"

    def test_read_user_hides_other_members_answers(self, authenticated_client, teammate_id):
        response = authenticated_client.get(f"/users/{teammate_id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["user_settings"]["onboarding"]["profile"] is None

    def test_read_user_shows_own_answers(self, authenticated_client, authenticated_user_id):
        authenticated_client.patch(
            "/users/settings", json={"onboarding": {"profile": self.PROFILE}}
        )

        response = authenticated_client.get(f"/users/{authenticated_user_id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["user_settings"]["onboarding"]["profile"]["job_role"] == "qa"
