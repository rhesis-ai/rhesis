from enum import Enum
from typing import Type

from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.models.user import User


class Visibility(Enum):
    PUBLIC = "public"
    PRIVATE = "private"


class ResourceAction(Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"


class ResourcePermission:
    def __init__(self, resource_model: Type, user: User, db: Session):
        self.resource_model = resource_model
        self.user = user
        self.db = db

    def can_access(self, resource_id: str, action: ResourceAction) -> bool:
        # Apply organization filtering if model supports it and user is not superuser (SECURITY CRITICAL)
        query = self.db.query(self.resource_model).filter_by(id=resource_id)

        if (
            not self.user.is_superuser
            and hasattr(self.resource_model, "organization_id")
            and self.user.organization_id
        ):
            query = query.filter_by(organization_id=self.user.organization_id)

        resource = query.first()
        if not resource:
            return False

        # Public resources can be read by anyone
        if (
            hasattr(resource, "visibility")
            and getattr(resource, "visibility") == Visibility.PUBLIC.value
            and action == ResourceAction.READ
        ):
            return True

        # Check organization access
        if (
            hasattr(resource, "organization_id")
            and resource.organization_id == self.user.organization_id
        ):
            return True

        # Resource owners can do anything with their resources
        if hasattr(resource, "user_id") and resource.user_id == self.user.id:
            return True

        # Superusers can do anything
        if self.user.is_superuser:
            return True

        return False

    def validate_access(self, resource_id: str, action: ResourceAction) -> None:
        if not self.can_access(resource_id, action):
            raise HTTPException(
                status_code=403, detail=f"Not authorized to {action.value} this resource"
            )
