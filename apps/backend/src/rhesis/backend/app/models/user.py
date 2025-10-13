from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from typing import Optional
import uuid

from rhesis.backend.app.models.guid import GUID

from .base import Base


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
    auth0_id = Column(String, nullable=True)
    organization_id = Column(GUID(), ForeignKey("organization.id"), nullable=True)
    last_login_at = Column(DateTime, nullable=True)  # Track when user last logged in
    user_settings = Column(
        JSONB,
        nullable=False,
        server_default='{"version": 1, "llm_defaults": {"generation": {}, "evaluation": {}}}',
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

    # Comment relationships
    comments = relationship("Comment", back_populates="user")

    # Task relationships
    assigned_tasks = relationship(
        "Task", foreign_keys="[Task.assignee_id]", back_populates="assignee"
    )

    @classmethod
    def from_auth0(cls, userinfo: dict) -> "User":
        """Create a User instance from Auth0 userinfo"""
        return cls(
            auth0_id=userinfo["sub"],
            email=userinfo["email"],
            name=userinfo.get("name"),
            picture=userinfo.get("picture"),
            given_name=userinfo.get("given_name"),
            family_name=userinfo.get("family_name"),
        )

    @property
    def display_name(self) -> str:
        """Returns the best available display name"""
        return self.name or self.email

    def to_dict(self) -> dict:
        """Convert to dictionary for session storage"""
        return {
            "id": str(self.id),
            "auth0_id": self.auth0_id,
            "email": self.email,
            "name": self.name,
            "given_name": self.given_name,
            "family_name": self.family_name,
            "picture": self.picture,
            "is_active": self.is_active,
            "is_superuser": self.is_superuser,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
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

    # User settings helper methods
    def get_generation_model_id(self) -> Optional[uuid.UUID]:
        """Get the user's preferred model ID for test generation"""
        if not self.user_settings:
            return None
        model_id = self.user_settings.get("llm_defaults", {}).get("generation", {}).get("model_id")
        if model_id:
            return uuid.UUID(model_id) if isinstance(model_id, str) else model_id
        return None

    def get_evaluation_model_id(self) -> Optional[uuid.UUID]:
        """Get the user's preferred model ID for LLM-as-judge evaluation"""
        if not self.user_settings:
            return None
        model_id = self.user_settings.get("llm_defaults", {}).get("evaluation", {}).get("model_id")
        if model_id:
            return uuid.UUID(model_id) if isinstance(model_id, str) else model_id
        return None

    def get_generation_settings(self) -> dict:
        """Get all generation-related settings"""
        if not self.user_settings:
            return {}
        return self.user_settings.get("llm_defaults", {}).get("generation", {})

    def get_evaluation_settings(self) -> dict:
        """Get all evaluation-related settings"""
        if not self.user_settings:
            return {}
        return self.user_settings.get("llm_defaults", {}).get("evaluation", {})

    def update_settings(self, updates: dict) -> None:
        """
        Deep merge updates into existing settings.
        
        Args:
            updates: Dictionary of settings to update (will be deep merged)
        
        Example:
            user.update_settings({
                "llm_defaults": {
                    "generation": {
                        "model_id": "uuid-string",
                        "temperature": 0.7
                    }
                }
            })
        """
        from copy import deepcopy

        current = deepcopy(self.user_settings or {})
        self.user_settings = self._deep_merge(current, updates)

    @staticmethod
    def _deep_merge(base: dict, updates: dict) -> dict:
        """Deep merge two dictionaries"""
        result = base.copy()
        for key, value in updates.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = User._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
