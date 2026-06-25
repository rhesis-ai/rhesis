"""Tests for session regeneration utility."""

from unittest.mock import MagicMock

from rhesis.backend.app.auth.session_utils import regenerate_session


class TestRegenerateSession:
    """Test session regeneration (fixation prevention)."""

    def test_clears_and_repopulates(self):
        request = MagicMock()
        request.session = {"old_key": "old_value", "other": "data"}

        regenerate_session(request, {"user_id": "new-user"})

        # Old keys should be gone, only new_data remains
        assert "old_key" not in request.session
        assert "other" not in request.session
        assert request.session["user_id"] == "new-user"

    def test_empty_new_data_just_clears(self):
        request = MagicMock()
        request.session = {"key": "value"}

        regenerate_session(request, {})

        assert len(request.session) == 0
