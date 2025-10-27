import inspect
from functools import wraps
from typing import Callable, Type, TypeVar

from fastapi import Response

from rhesis.backend.app.utils.crud_utils import count_items
from rhesis.backend.logging import logger

T = TypeVar("T")


def with_count_header(model: Type):
    def decorator(func: Callable) -> Callable:
        is_async = inspect.iscoroutinefunction(func)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            response: Response = kwargs["response"]
            filter_expr = kwargs.get("filter")

            # Get dependencies - all endpoints now use this pattern
            db = kwargs.get("db")
            tenant_context = kwargs.get("tenant_context")

            if db and tenant_context:
                # Standard pattern: db + tenant_context
                organization_id, user_id = tenant_context
                count = count_items(db, model, filter_expr, organization_id, user_id)
                response.headers["X-Total-Count"] = str(count)
            else:
                # Missing required dependencies - cannot count items without organization filtering
                # This is a security requirement to prevent data leakage across organizations
                logger.warning(f"Cannot count {model.__name__} items without organization context")
                response.headers["X-Total-Count"] = "0"

            # Call original route function (await if async)
            result = await func(*args, **kwargs) if is_async else func(*args, **kwargs)
            return result

        return wrapper

    return decorator
