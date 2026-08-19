"""Unit tests for create_session_token's token-exchange-issued claims.

No DB needed -- create_session_token only reads attributes off the
User it is handed, so a SimpleNamespace stands in for the ORM model,
mirroring the mocking pattern in test_token_utils_email_flow.py.
"""

from types import SimpleNamespace
from unittest.mock import patch

import jwt
import pytest

from rhesis.backend.app.auth.token_utils import create_session_token, get_jwt_algorithm

SECRET = "test-secret-key-for-tests"


def _user(**overrides):
    base = dict(
        id="11111111-1111-1111-1111-111111111111",
        organization_id="22222222-2222-2222-2222-222222222222",
        email="user@example.com",
        name="Test User",
        picture=None,
        is_email_verified=True,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.unit
@patch("rhesis.backend.app.auth.token_utils.get_secret_key", return_value=SECRET)
class TestCreateSessionTokenProjectClaim:
    """Tests for the ``project`` claim added alongside azp/scope/jti/epoch."""

    def test_default_path_has_no_project_claim(self, mock_secret):
        """No kwargs at all -- byte-identical default payload, no project key."""
        token = create_session_token(_user())
        payload = jwt.decode(
            token, SECRET, algorithms=[get_jwt_algorithm()], options={"verify_exp": False}
        )
        assert "project" not in payload
        assert "azp" not in payload

    def test_project_claim_set_when_azp_present(self, mock_secret):
        project_id = "33333333-3333-3333-3333-333333333333"
        token = create_session_token(
            _user(),
            azp="warehouse-sync",
            epoch=0,
            project=project_id,
        )
        # azp implies an aud claim; verify_aud=False because this test only
        # cares about the project claim, not the audience contract.
        payload = jwt.decode(
            token,
            SECRET,
            algorithms=[get_jwt_algorithm()],
            options={"verify_exp": False, "verify_aud": False},
        )
        assert payload["project"] == project_id

    def test_no_project_claim_when_resource_omitted(self, mock_secret):
        """Exchanging with no ``resource`` mints a token with no project claim."""
        token = create_session_token(_user(), azp="warehouse-sync", epoch=0, project=None)
        payload = jwt.decode(
            token,
            SECRET,
            algorithms=[get_jwt_algorithm()],
            options={"verify_exp": False, "verify_aud": False},
        )
        assert "project" not in payload

    def test_project_without_azp_raises(self, mock_secret):
        """project only has meaning alongside azp, same as scope/jti/epoch."""
        with pytest.raises(ValueError, match="require azp"):
            create_session_token(_user(), project="33333333-3333-3333-3333-333333333333")
