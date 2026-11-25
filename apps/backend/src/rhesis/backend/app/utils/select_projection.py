"""OData ``$select`` for list routes, applied in one place to the serialized response.

A route opts in by declaring a ``$select`` query parameter and otherwise returns its
results as usual. :func:`apply_select_projection` wraps every such route so that, once
the route's ``response_model`` has serialized the response, only the selected top-level
fields are kept. ``$select`` can therefore narrow a response but never add to it.
"""

import json
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.routing import APIRoute, request_response

SELECT_PARAM = "$select"


def selected_fields(select: str | None) -> set[str] | None:
    """The top-level fields a ``$select`` keeps (``id`` included), or ``None`` for all."""
    if not select:
        return None
    fields = {f.strip() for f in select.split(",") if f.strip()}
    fields.add("id")
    return fields


def apply_select(data: Any, select: str | None) -> Any:
    """Keep only the selected top-level fields of serialized JSON. ``id`` is always kept.

    *data* is already-serialized JSON (a dict, or a list of them). Anything that is not
    a dict is returned unchanged.
    """
    fields = selected_fields(select)
    if fields is None:
        return data

    def pick(item: Any) -> Any:
        if not isinstance(item, dict):
            return item
        return {k: v for k, v in item.items() if k in fields}

    if isinstance(data, list):
        return [pick(item) for item in data]
    return pick(data)


def route_supports_select(route: APIRoute) -> bool:
    return any(param.alias == SELECT_PARAM for param in route.dependant.query_params)


def _projecting(
    handler: Callable[[Request], Awaitable[Response]],
) -> Callable[[Request], Awaitable[Response]]:
    async def project(request: Request) -> Response:
        response = await handler(request)
        select = request.query_params.get(SELECT_PARAM)
        content_type = response.headers.get("content-type", "")
        if not select or not 200 <= response.status_code < 300:
            return response
        if not content_type.startswith("application/json"):
            return response
        # Streaming responses have no body attribute; a 204 has an empty one.
        if not getattr(response, "body", None):
            return response
        projected = apply_select(json.loads(response.body), select)
        # Same encoding as starlette's JSONResponse; FastAPI may hand back a plain Response.
        response.body = json.dumps(
            projected, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode("utf-8")
        response.headers["content-length"] = str(len(response.body))
        return response

    return project


def apply_select_projection(app: FastAPI) -> None:
    """Apply ``$select`` to the serialized response of every route that declares it.

    Post-hoc, like the auth backstops in ``main.py``: ``include_router`` copies routes
    with their own class, so a custom ``route_class`` would not reach EE routers. Must be
    called after every router is registered.
    """
    for route in app.router.routes:
        if isinstance(route, APIRoute) and route_supports_select(route):
            route.app = request_response(_projecting(route.get_route_handler()))
