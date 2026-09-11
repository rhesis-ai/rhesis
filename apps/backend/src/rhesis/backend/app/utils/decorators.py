import inspect
import logging
from functools import wraps
from typing import Callable, Optional, Type, TypeVar

import anyio
from fastapi import Response
from starlette.responses import Response as StarletteResponse

from rhesis.backend.app.utils.crud_utils import count_items

logger = logging.getLogger(__name__)

T = TypeVar("T")


def with_count_header(
    model: Type,
    exclude_explorer_rows: bool = False,
    extra_filter: Optional[Callable] = None,
):
    """Set X-Total-Count for a list endpoint.

    Pass ``exclude_explorer_rows=True`` when the endpoint itself hides Explorer-owned
    rows, so the header matches what the page returns.

    `extra_filter` does the same job for any other hidden rows (e.g.
    metric-owned ones) and must mirror whatever the route's list query applies,
    or the header will not agree with the rows the client can page through.

    The wrapper keeps the handler's sync/async nature. FastAPI decides between the
    event loop and the threadpool by looking at the wrapper, so an async wrapper
    around a ``def`` handler would put the count query and every query in the
    handler on the event loop.
    """

    def _set_count_header(kwargs: dict) -> None:
        response: Response = kwargs["response"]
        filter_expr = kwargs.get("filter")

        # Get dependencies - all endpoints now use this pattern
        db = kwargs.get("db")
        tenant_context = kwargs.get("tenant_context")

        if db and tenant_context:
            # Standard pattern: db + tenant_context
            organization_id, user_id = tenant_context
            count = count_items(
                db,
                model,
                filter_expr,
                organization_id,
                user_id,
                exclude_explorer_rows=exclude_explorer_rows,
                extra_filter=extra_filter,
            )
            response.headers["X-Total-Count"] = str(count)
        else:
            # Missing required dependencies - cannot count items without organization filtering
            # This is a security requirement to prevent data leakage across organizations
            logger.warning(f"Cannot count {model.__name__} items without organization context")
            response.headers["X-Total-Count"] = "0"

    def _forward_headers(result, response: Response):
        # When the route returns a Response directly (e.g. JSONResponse for $select paths),
        # FastAPI forwards it as-is and ignores headers set on the `response` dependency.
        # Copy the count header so it is never silently dropped.
        if isinstance(result, StarletteResponse):
            for header_name, header_value in response.headers.items():
                result.headers.setdefault(header_name, header_value)
        return result

    def decorator(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                await anyio.to_thread.run_sync(_set_count_header, kwargs)
                result = await func(*args, **kwargs)
                return _forward_headers(result, kwargs["response"])

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            _set_count_header(kwargs)
            result = func(*args, **kwargs)
            return _forward_headers(result, kwargs["response"])

        return sync_wrapper

    return decorator
