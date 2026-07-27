from typing import Optional

from fastapi import APIRouter


class RhesisRouter(APIRouter):
    """APIRouter subclass that stamps a resource name onto every route it owns.

    Usage::

        router = RhesisRouter(prefix="/behaviors", tags=["behaviors"], resource="behavior")

    The ``resource`` name is stored in ``route.openapi_extra["x-rhesis-resource"]``
    on every route added to this router.  The capability deriver in
    :mod:`rhesis.backend.app.auth.capabilities` reads it to derive
    ``"behavior:read"``, ``"behavior:create"``, etc. without any hardcoded
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
