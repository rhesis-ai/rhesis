import inspect
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
            db: Session = kwargs["db"]
            filter_expr = kwargs.get("filter")

            # Perform count
            count = count_items(db, model, filter_expr)
            response.headers["X-Total-Count"] = str(count)

            # Call original route function (await if async)
            result = await func(*args, **kwargs) if is_async else func(*args, **kwargs)
            return result

        return wrapper

    return decorator
