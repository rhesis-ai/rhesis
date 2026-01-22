from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from rhesis.backend.app.models.guid import GUID
from rhesis.backend.app.models.user_settings import UserSettingsManager

from .base import Base

if TYPE_CHECKING:
    from rhesis.backend.app.auth.providers.base import AuthUser


class User(Base):
    __tablename__ = "user"

    # User-specific columns
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    given_name = Column(String, nullable=True)
    family_name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)  # To track if the user is active or not
    is_superuser = Column(Boolean, default=False)  # Admin flag
    is_verified = Column(Boolean, default=False)  # To track if the user is verified or not
    auth0_id = Column(String, nullable=True)  # Legacy: kept for migration, will be removed
    organization_id = Column(GUID(), ForeignKey("organization.id"), nullable=True)
    last_login_at = Column(DateTime, nullable=True)  # Track when user last logged in

    # Native authentication columns (provider-agnostic)
    provider_type = Column(
        String(50),
        nullable=True,
        index=True,
        comment="Authentication provider type (google, github, email, etc.)",
    )
    external_provider_id = Column(
        String(255),
        nullable=True,
        comment="External ID from the authentication provider",
    )
    password_hash = Column(
        String(255),
        nullable=True,
        comment="Bcrypt password hash for email/password authentication",
    )
    user_settings = Column(
        JSONB,
        nullable=False,
        server_default='{"version": 1, "models": {"generation": {}, "evaluation": {}}}',
    )  # User preferences and settings

    # Relationship to subscriptions
    subscriptions = relationship("Subscription", back_populates="user")
    prompt_templates = relationship("PromptTemplate", back_populates="user")
    prompts = relationship("Prompt", back_populates="user")
    test_configurations = relationship("TestConfiguration", back_populates="user")
    test_results = relationship("TestResult", back_populates="user")
    test_sets = relationship("TestSet", foreign_keys="[TestSet.user_id]", back_populates="user")
    test_runs = relationship("TestRun", foreign_keys="[TestRun.user_id]", back_populates="user")
    endpoints = relationship("Endpoint", back_populates="user")

    tokens = relationship("Token", back_populates="user")
    organization = relationship(
        "Organization", back_populates="users", foreign_keys="[User.organization_id]"
    )

    # Add these relationships to the User class
    created_projects = relationship(
        "Project", foreign_keys="[Project.user_id]", back_populates="user"
    )
    owned_projects = relationship(
        "Project", foreign_keys="[Project.owner_id]", back_populates="owner"
    )
    created_tests = relationship("Test", foreign_keys="[Test.user_id]", back_populates="user")
    assigned_tests = relationship(
        "Test", foreign_keys="[Test.assignee_id]", back_populates="assignee"
    )
    owned_tests = relationship("Test", foreign_keys="[Test.owner_id]", back_populates="owner")

    # Test Set relationships
    owned_test_sets = relationship(
        "TestSet", foreign_keys="[TestSet.owner_id]", back_populates="owner"
    )
    assigned_test_sets = relationship(
        "TestSet", foreign_keys="[TestSet.assignee_id]", back_populates="assignee"
    )

    # Test Run relationships
    owned_test_runs = relationship(
        "TestRun", foreign_keys="[TestRun.owner_id]", back_populates="owner"
    )
    assigned_test_runs = relationship(
        "TestRun", foreign_keys="[TestRun.assignee_id]", back_populates="assignee"
    )

    # Metric relationships
    assigned_metrics = relationship(
        "Metric", foreign_keys="[Metric.assignee_id]", back_populates="assignee"
    )
    owned_metrics = relationship("Metric", foreign_keys="[Metric.owner_id]", back_populates="owner")

    # Model relationships
    owned_models = relationship("Model", foreign_keys="[Model.owner_id]", back_populates="owner")
    assigned_models = relationship(
        "Model", foreign_keys="[Model.assignee_id]", back_populates="assignee"
    )

    # Source relationships
    created_sources = relationship("Source", foreign_keys="[Source.user_id]", back_populates="user")

    # Task relationships
    assigned_tasks = relationship(
        "Task", foreign_keys="[Task.assignee_id]", back_populates="assignee"
    )

    # Comment relationships
    comments = relationship("Comment", back_populates="user")

    # Tool relationships
    tools = relationship("Tool", foreign_keys="[Tool.user_id]", back_populates="user")

    @classmethod
    def from_auth0(cls, userinfo: dict) -> "User":
        """Create a User instance from Auth0 userinfo (legacy, kept for migration)"""
        return cls(
            auth0_id=userinfo["sub"],
            email=userinfo["email"],
            name=userinfo.get("name"),
            picture=userinfo.get("picture"),
            given_name=userinfo.get("given_name"),
            family_name=userinfo.get("family_name"),
        )

    @classmethod
    def from_auth_user(cls, auth_user: "AuthUser") -> "User":
        """
        Create a User instance from an AuthUser (provider-agnostic).

        Args:
            auth_user: AuthUser dataclass from any authentication provider

        Returns:
            User instance with provider information populated
        """
        # Import here to avoid circular imports
        from rhesis.backend.app.auth.providers.base import AuthUser

        if not isinstance(auth_user, AuthUser):
            raise TypeError(f"Expected AuthUser, got {type(auth_user)}")

        return cls(
            email=auth_user.email,
            name=auth_user.name,
            given_name=auth_user.given_name,
            family_name=auth_user.family_name,
            picture=auth_user.picture,
            provider_type=auth_user.provider_type,
            external_provider_id=auth_user.external_id,
        )

    @property
    def display_name(self) -> str:
        """Returns the best available display name"""
        return self.name or self.email

    def to_dict(self) -> dict:
        """Convert to dictionary for session storage"""
        return {
            "id": str(self.id),
            "auth0_id": self.auth0_id,  # Legacy, kept for backward compatibility
            "email": self.email,
            "name": self.name,
            "given_name": self.given_name,
            "family_name": self.family_name,
            "picture": self.picture,
            "is_active": self.is_active,
            "is_superuser": self.is_superuser,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "provider_type": self.provider_type,
            "external_provider_id": self.external_provider_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """Create a User instance from session data"""
        # Handle datetime field conversion if present
        if "last_login_at" in data and data["last_login_at"]:
            from datetime import datetime

            if isinstance(data["last_login_at"], str):
                data["last_login_at"] = datetime.fromisoformat(data["last_login_at"])
        return cls(**data)

    @property
    def settings(self) -> UserSettingsManager:
        """
        Centralized access to user settings.

        Provides a clean interface for accessing and updating all user preferences.
        The settings manager instance is cached for the lifetime of the User object,
        and updates are automatically persisted to the database.

        Usage:
            # Access model settings
            model_id = user.settings.models.generation.model_id
            temperature = user.settings.models.generation.temperature
            eval_model = user.settings.models.evaluation.model_id

            # Access UI settings
            theme = user.settings.ui.theme
            page_size = user.settings.ui.default_page_size

            # Update settings (auto-persists!)
            user.settings.update({
                "models": {
                    "generation": {"model_id": str(model.id), "temperature": 0.7}
                }
            })
            # No manual persistence needed - changes are applied immediately
        """
        # Cache the manager instance to prevent creating new instances on each access
        # Pass self to enable auto-persistence when updates are made
        if not hasattr(self, "_settings_cache") or self._settings_cache is None:
            self._settings_cache = UserSettingsManager(self.user_settings, user_instance=self)
        return self._settings_cache


# Event listener to invalidate settings cache when user_settings is modified
@event.listens_for(User.user_settings, "set", propagate=True)
def _invalidate_settings_cache(target, value, oldvalue, initiator):
    """Invalidate the cached settings manager when user_settings changes."""
    if hasattr(target, "_settings_cache"):
        target._settings_cache = None
