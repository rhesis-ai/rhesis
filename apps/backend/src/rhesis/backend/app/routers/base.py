from typing import Any, Callable, Optional

from fastapi import APIRouter


class RhesisRouter(APIRouter):
    """APIRouter subclass that stamps a resource name onto every route it owns.

    Usage::

        router = RhesisRouter(prefix="/requirements", tags=["requirements"], resource="requirement")

    The ``resource`` name is stored in ``route.openapi_extra["x-rhesis-resource"]``
    on every route added to this router.  The capability deriver in
    :mod:`rhesis.backend.app.auth.capabilities` reads it to derive
    ``"requirement:read"``, ``"requirement:create"``, etc. without any hardcoded
    tag-to-resource mapping.

    Non-CRUD routes whose action cannot be inferred from the HTTP verb should
    carry an explicit ``@capability("resource:action")`` decorator instead::

        @router.post("/generate", **capability("test_set:generate"))
        async def generate(...): ...
    """

    def __init__(self, *args, resource: Optional[str] = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._rhesis_resource = resource

    def add_api_route(self, path: str, endpoint, **kwargs) -> None:  # type: ignore[override]
        if self._rhesis_resource:
            extra: dict = dict(kwargs.pop("openapi_extra", None) or {})
            # setdefault: an explicit @capability() marker already in the dict wins.
            extra.setdefault("x-rhesis-resource", self._rhesis_resource)
            kwargs["openapi_extra"] = extra
        super().add_api_route(path, endpoint, **kwargs)


_FIRST_DEPENDENCY_ATTR = "__rhesis_first_dependency__"


def run_first(dependency: Callable[..., Any]):
    """Mark an endpoint so ``dependency`` is solved before every other one, auth included.

    For admission control that must turn a request away before it costs a
    database connection; ``main.apply_first_dependencies`` does the insertion
    once the auth backstops are in place. The endpoint can also declare
    ``Depends(dependency)`` to receive its value: FastAPI solves it once per request.
    """

    def mark(endpoint):
        setattr(endpoint, _FIRST_DEPENDENCY_ATTR, dependency)
        return endpoint

    return mark


def first_dependency_of(endpoint: Any) -> Optional[Callable[..., Any]]:
    return getattr(endpoint, _FIRST_DEPENDENCY_ATTR, None)
