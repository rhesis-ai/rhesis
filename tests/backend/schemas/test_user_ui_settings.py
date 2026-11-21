"""Schema tests for the user's UI settings."""

import pytest
from pydantic import ValidationError

from rhesis.backend.app.schemas.user import UserSettingsUpdate


class TestAccessibilityMode:
    def test_is_writable_on_its_own(self):
        """✅ Turning the mode on leaves the other UI settings alone."""
        update = UserSettingsUpdate(ui={"accessibility_mode": True})

        assert update.model_dump(exclude_unset=True, mode="json") == {
            "ui": {"accessibility_mode": True}
        }

    def test_rejects_a_non_boolean(self):
        """❌ Only a real on/off switch is stored."""
        with pytest.raises(ValidationError):
            UserSettingsUpdate(ui={"accessibility_mode": "sometimes"})
