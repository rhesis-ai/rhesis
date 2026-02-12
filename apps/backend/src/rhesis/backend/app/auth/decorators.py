from functools import wraps
from typing import Type

from rhesis.backend.app.auth.permissions import ResourceAction, ResourcePermission
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db


def check_resource_permission(resource_model: Type, action: ResourceAction):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get dependencies
            db = kwargs.get("db")
            current_user = kwargs.get("current_user") or require_current_user_or_token()

            # Get resource_id from path parameters
            resource_id = None
            for key in kwargs:
                if key.endswith("_id") or key.endswith("_identifier"):
                    resource_id = kwargs[key]
                    break

            if resource_id:
                if db is not None:
                    permission = ResourcePermission(resource_model, current_user, db)
                    permission.validate_access(resource_id, action)
                else:
                    with get_db() as fallback_db:
                        permission = ResourcePermission(resource_model, current_user, fallback_db)
                        permission.validate_access(resource_id, action)

            return await func(*args, **kwargs)

        return wrapper

    return decorator
