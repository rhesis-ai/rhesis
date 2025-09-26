import inspect
from contextlib import contextmanager
from functools import wraps
from typing import Callable, Type, TypeVar

from fastapi import Response
from sqlalchemy.orm import Session

from rhesis.backend.app.utils.crud_utils import count_items

T = TypeVar("T")


def with_count_header(model: Type):
    def decorator(func: Callable) -> Callable:
        is_async = inspect.iscoroutinefunction(func)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            response: Response = kwargs["response"]
            db_context = kwargs["db"]
            filter_expr = kwargs.get("filter")
            
            # Extract tenant context if available
            tenant_context = kwargs.get("tenant_context")
            organization_id = None
            user_id = None
            if tenant_context:
                organization_id, user_id = tenant_context

            # Handle both Session objects and context managers
            if hasattr(db_context, 'query'):
                # Already a Session object
                db = db_context
                count = count_items(db, model, filter_expr, organization_id, user_id)
                response.headers["X-Total-Count"] = str(count)
            else:
                # It's a context manager, need to enter it to get the Session
                with db_context as db:
                    count = count_items(db, model, filter_expr, organization_id, user_id)
                    response.headers["X-Total-Count"] = str(count)

            # Call original route function (await if async)
            result = await func(*args, **kwargs) if is_async else func(*args, **kwargs)
            return result

        return wrapper

    return decorator
