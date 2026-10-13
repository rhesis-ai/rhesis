"""
👤 User.settings property tests

Run with: python -m pytest tests/backend/models/test_user_settings.py -v
"""

from fastapi.encoders import jsonable_encoder

from rhesis.backend.app.models.tag import Tag
from rhesis.backend.app.models.user import User


class TestUserSettingsProperty:
    def test_a_row_holding_the_user_serializes_after_settings_is_read(self):
        """✅ Reading `user.settings` leaves no cycle for `jsonable_encoder` to walk."""
        user = User(email="a@example.com", user_settings={"version": 1, "ui": {}})
        assert user.settings.ui.theme is None
        tag = Tag(name="urgent", user=user)

        assert jsonable_encoder(tag)["user"]["email"] == "a@example.com"

    def test_update_through_the_property_persists(self):
        """✅ `user.settings.update` writes back, and the next read sees it."""
        user = User(email="a@example.com", user_settings={"version": 1, "ui": {}})

        user.settings.update({"ui": {"theme": "dark"}})

        assert user.user_settings["ui"]["theme"] == "dark"
        assert user.settings.ui.theme == "dark"

    def test_reassigning_the_column_shows_in_the_next_read(self):
        """✅ No stale manager survives a direct write to the column."""
        user = User(email="a@example.com", user_settings={"version": 1, "ui": {}})
        assert user.settings.ui.theme is None

        user.user_settings = {"version": 1, "ui": {"theme": "light"}}

        assert user.settings.ui.theme == "light"
