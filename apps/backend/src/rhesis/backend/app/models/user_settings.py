"""User Settings Manager - Centralized access to user preferences and settings."""

import uuid
from typing import TYPE_CHECKING, Optional

# Avoid circular imports
if TYPE_CHECKING:
    from rhesis.backend.app.models.user import User


class UserSettingsManager:
    """
    Centralized manager for accessing and updating user settings.

    Provides a clean interface for working with user preferences without
    cluttering the User model with individual getter/setter methods.

    When created with a user instance reference, updates are automatically
    persisted to the database.

    Usage:
        user = await get_user(db, user_id)

        # Access model settings
        model_id = user.settings.models.generation.model_id
        temp = user.settings.models.generation.temperature

        # Access UI settings
        theme = user.settings.ui.theme

        # Update settings (auto-persists when created from User.settings)
        user.settings.update({
            "models": {
                "generation": {"model_id": str(model.id)}
            }
        })
    """

    def __init__(self, settings_dict: dict, user_instance: Optional["User"] = None):
        """
        Initialize settings manager with user's settings dictionary.

        Args:
            settings_dict: The user_settings JSONB data from database
            user_instance: Optional reference to User instance for auto-persistence
        """
        self._data = settings_dict or self._default_settings()
        self._user = user_instance

    @staticmethod
    def _default_settings() -> dict:
        """Return default settings structure."""
        return {
            "version": 1,
            "models": {"generation": {}, "evaluation": {}},
        }

    @property
    def raw(self) -> dict:
        """Get raw settings dictionary."""
        return self._data

    @property
    def models(self) -> "ModelsSettingsAccessor":
        """Access model-related settings."""
        return ModelsSettingsAccessor(self._data.get("models", {}))

    @property
    def ui(self) -> "UISettingsAccessor":
        """Access UI-related settings."""
        return UISettingsAccessor(self._data.get("ui", {}))

    @property
    def notifications(self) -> "NotificationSettingsAccessor":
        """Access notification settings."""
        return NotificationSettingsAccessor(self._data.get("notifications", {}))

    @property
    def localization(self) -> "LocalizationSettingsAccessor":
        """Access localization settings."""
        return LocalizationSettingsAccessor(self._data.get("localization", {}))

    @property
    def privacy(self) -> "PrivacySettingsAccessor":
        """Access privacy settings."""
        return PrivacySettingsAccessor(self._data.get("privacy", {}))

    def update(self, updates: dict) -> dict:
        """
        Deep merge updates into settings.

        When the manager has a user instance reference, changes are automatically
        persisted to the database. Otherwise, manual persistence is required.

        Args:
            updates: Dictionary of settings to update

        Returns:
            Updated settings dictionary

        Example:
            # Auto-persists when using user.settings
            user.settings.update({
                "models": {
                    "generation": {"model_id": "uuid", "temperature": 0.7}
                }
            })
        """
        self._data = self._deep_merge(self._data, updates)

        # Auto-persist if we have a user reference
        if self._user is not None:
            self._user.user_settings = self._data

        return self._data

    @staticmethod
    def _deep_merge(base: dict, updates: dict) -> dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        for key, value in updates.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = UserSettingsManager._deep_merge(result[key], value)
            else:
                result[key] = value
        return result


class ModelsSettingsAccessor:
    """Accessor for model-related settings."""

    def __init__(self, models_settings: dict):
        self._data = models_settings

    @property
    def generation(self) -> "ModelSettingsAccessor":
        """Access generation model settings."""
        return ModelSettingsAccessor(self._data.get("generation", {}))

    @property
    def evaluation(self) -> "ModelSettingsAccessor":
        """Access evaluation model settings."""
        return ModelSettingsAccessor(self._data.get("evaluation", {}))


class ModelSettingsAccessor:
    """Accessor for individual model settings (generation or evaluation)."""

    def __init__(self, model_settings: dict):
        self._data = model_settings

    @property
    def model_id(self) -> Optional[uuid.UUID]:
        """Get the model ID as UUID object."""
        model_id = self._data.get("model_id")
        if model_id:
            return uuid.UUID(model_id) if isinstance(model_id, str) else model_id
        return None

    @property
    def fallback_model_id(self) -> Optional[uuid.UUID]:
        """Get the fallback model ID as UUID object."""
        model_id = self._data.get("fallback_model_id")
        if model_id:
            return uuid.UUID(model_id) if isinstance(model_id, str) else model_id
        return None

    @property
    def temperature(self) -> Optional[float]:
        """Get temperature setting."""
        return self._data.get("temperature")

    @property
    def max_tokens(self) -> Optional[int]:
        """Get max tokens setting."""
        return self._data.get("max_tokens")

    @property
    def all(self) -> dict:
        """Get all settings as dictionary."""
        return self._data


class UISettingsAccessor:
    """Accessor for UI settings."""

    def __init__(self, ui_settings: dict):
        self._data = ui_settings

    @property
    def theme(self) -> Optional[str]:
        """Get UI theme ('light', 'dark', or 'auto')."""
        return self._data.get("theme")

    @property
    def density(self) -> Optional[str]:
        """Get UI density ('compact', 'comfortable', or 'spacious')."""
        return self._data.get("density")

    @property
    def sidebar_collapsed(self) -> Optional[bool]:
        """Get sidebar collapsed state."""
        return self._data.get("sidebar_collapsed")

    @property
    def default_page_size(self) -> Optional[int]:
        """Get default pagination size."""
        return self._data.get("default_page_size")


class NotificationSettingsAccessor:
    """Accessor for notification settings."""

    def __init__(self, notification_settings: dict):
        self._data = notification_settings

    @property
    def email(self) -> dict:
        """Get email notification settings."""
        return self._data.get("email", {})

    @property
    def in_app(self) -> dict:
        """Get in-app notification settings."""
        return self._data.get("in_app", {})


class LocalizationSettingsAccessor:
    """Accessor for localization settings."""

    def __init__(self, localization_settings: dict):
        self._data = localization_settings

    @property
    def language(self) -> Optional[str]:
        """Get preferred language code."""
        return self._data.get("language")

    @property
    def timezone(self) -> Optional[str]:
        """Get user timezone."""
        return self._data.get("timezone")

    @property
    def date_format(self) -> Optional[str]:
        """Get preferred date format."""
        return self._data.get("date_format")

    @property
    def time_format(self) -> Optional[str]:
        """Get preferred time format."""
        return self._data.get("time_format")


class PrivacySettingsAccessor:
    """Accessor for privacy settings."""

    def __init__(self, privacy_settings: dict):
        self._data = privacy_settings

    @property
    def show_email(self) -> Optional[bool]:
        """Get show email setting."""
        return self._data.get("show_email")

    @property
    def show_activity(self) -> Optional[bool]:
        """Get show activity setting."""
        return self._data.get("show_activity")
