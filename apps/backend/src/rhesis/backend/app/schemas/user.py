from datetime import datetime
from typing import Optional

from pydantic import UUID4, BaseModel, ConfigDict, Field, field_validator

from rhesis.backend.app.schemas import Base


# User Settings schemas - use BaseModel instead of Base since these are not DB models
class LLMModelSettings(BaseModel):
    """Settings for a specific LLM use case (generation or evaluation)"""

    model_id: Optional[UUID4] = Field(None, description="ID of the preferred Model")
    fallback_model_id: Optional[UUID4] = Field(
        None, description="ID of fallback Model if primary fails"
    )
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Temperature override")
    max_tokens: Optional[int] = Field(None, gt=0, description="Max tokens override")


class ModelsSettings(BaseModel):
    """Model preferences and settings for different use cases"""

    generation: Optional[LLMModelSettings] = Field(
        default_factory=LLMModelSettings, description="Settings for test generation"
    )
    evaluation: Optional[LLMModelSettings] = Field(
        default_factory=LLMModelSettings, description="Settings for LLM-as-judge evaluation"
    )


class UISettings(BaseModel):
    """UI preferences"""

    theme: Optional[str] = Field(None, description="UI theme: 'light', 'dark', or 'auto'")
    density: Optional[str] = Field(
        None, description="UI density: 'compact', 'comfortable', or 'spacious'"
    )
    sidebar_collapsed: Optional[bool] = Field(None, description="Whether sidebar is collapsed")
    default_page_size: Optional[int] = Field(
        None, gt=0, le=100, description="Default pagination size"
    )


class EmailNotificationSettings(BaseModel):
    """Email notification preferences"""

    test_run_complete: Optional[bool] = None
    test_failures: Optional[bool] = None
    weekly_summary: Optional[bool] = None


class InAppNotificationSettings(BaseModel):
    """In-app notification preferences"""

    test_run_complete: Optional[bool] = None
    mentions: Optional[bool] = None


class NotificationSettings(BaseModel):
    """Notification preferences"""

    email: Optional[EmailNotificationSettings] = Field(default_factory=EmailNotificationSettings)
    in_app: Optional[InAppNotificationSettings] = Field(default_factory=InAppNotificationSettings)


class LocalizationSettings(BaseModel):
    """Localization preferences"""

    language: Optional[str] = Field(None, description="Preferred language code (e.g., 'en', 'es')")
    timezone: Optional[str] = Field(
        None, description="User timezone (e.g., 'UTC', 'America/New_York')"
    )
    date_format: Optional[str] = Field(None, description="Preferred date format")
    time_format: Optional[str] = Field(None, description="Preferred time format: '12h' or '24h'")


class PrivacySettings(BaseModel):
    """Privacy preferences"""

    show_email: Optional[bool] = Field(None, description="Show email to other users")
    show_activity: Optional[bool] = Field(None, description="Show activity status")


class OnboardingProgress(BaseModel):
    """Onboarding progress tracking"""

    project_created: bool = False
    endpoint_setup: bool = False
    users_invited: bool = False
    test_cases_created: bool = False
    dismissed: bool = False
    last_updated: Optional[datetime] = None


class PolyphemusAccess(BaseModel):
    """Polyphemus access tracking"""

    granted_at: Optional[datetime] = Field(None, description="When access was granted")
    revoked_at: Optional[datetime] = Field(None, description="When access was revoked")
    requested_at: Optional[datetime] = Field(None, description="When access was requested")


class UserSettings(BaseModel):
    """Complete user settings schema"""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(1, description="Settings schema version")
    models: Optional[ModelsSettings] = Field(default_factory=ModelsSettings)
    ui: Optional[UISettings] = Field(default_factory=UISettings)
    notifications: Optional[NotificationSettings] = Field(default_factory=NotificationSettings)
    localization: Optional[LocalizationSettings] = Field(default_factory=LocalizationSettings)
    privacy: Optional[PrivacySettings] = Field(default_factory=PrivacySettings)
    onboarding: Optional[OnboardingProgress] = Field(default_factory=OnboardingProgress)
    polyphemus_access: Optional[PolyphemusAccess] = Field(
        None, description="Polyphemus access information"
    )


class UserSettingsUpdate(BaseModel):
    """Schema for updating user settings (all fields optional for partial updates)"""

    model_config = ConfigDict(extra="forbid")

    models: Optional[ModelsSettings] = None
    ui: Optional[UISettings] = None
    notifications: Optional[NotificationSettings] = None
    localization: Optional[LocalizationSettings] = None
    privacy: Optional[PrivacySettings] = None
    onboarding: Optional[OnboardingProgress] = None
    polyphemus_access: Optional[PolyphemusAccess] = None


# User schemas
class UserBase(Base):
    email: str = Field(..., min_length=1, description="Email address cannot be empty")
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    auth0_id: Optional[str] = None
    picture: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    is_verified: Optional[bool] = None
    organization_id: Optional[UUID4] = None
    last_login_at: Optional[datetime] = None
    user_settings: Optional[UserSettings] = Field(
        default_factory=lambda: UserSettings(version=1), description="User preferences and settings"
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Email address cannot be empty or whitespace-only")
        return v.strip()


class UserCreate(UserBase):
    send_invite: Optional[bool] = False


class UserUpdate(UserBase):
    email: Optional[str] = None


class User(UserBase):
    pass


# For use in responses where we need minimal user info
class UserReference(Base):
    id: UUID4
    given_name: Optional[str] = ""  # Default to empty string to avoid validation errors
    family_name: Optional[str] = ""  # Default to empty string to avoid validation errors
    email: Optional[str] = ""  # Default to empty string to avoid validation errors
    picture: Optional[str] = ""  # Default to empty string to avoid validation errors

    model_config = ConfigDict(from_attributes=True)
