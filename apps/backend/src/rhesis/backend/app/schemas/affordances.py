from typing import List

from pydantic import BaseModel, Field


class WithPermittedActions(BaseModel):
    """Opt-in response mixin exposing server-resolved object-level affordances.

    ``permitted_actions`` lists the **full capability strings** (e.g.
    ``"comment:update"``, ``"comment:delete"``, ``"comment:react"``) the calling
    principal may perform on this specific object — the same vocabulary as
    ``GET /me/permissions``. Populated explicitly in the router via
    :func:`rhesis.backend.app.auth.affordances.populate_permitted_actions` —
    ``from_attributes=True`` does NOT auto-fill it, so it is an empty list on any
    response that does not opt in.
    """

    permitted_actions: List[str] = Field(default_factory=list)
