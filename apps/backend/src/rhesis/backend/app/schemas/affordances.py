from typing import List

from pydantic import BaseModel, Field


class WithPermittedActions(BaseModel):
    """Opt-in response mixin exposing server-resolved object-level affordances.

    ``permitted_actions`` lists the action names (capability middle-segment, e.g.
    ``"update"``, ``"delete"``, ``"react"``) the calling principal may perform on
    this specific object. Populated explicitly in the router via
    :func:`rhesis.backend.app.auth.affordances.populate_permitted_actions` —
    ``from_attributes=True`` does NOT auto-fill it, so it is an empty list on any
    response that does not opt in.
    """

    permitted_actions: List[str] = Field(default_factory=list)
