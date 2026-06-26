from typing import ClassVar, List, Optional

from pydantic import BaseModel, Field, model_validator


class WithPermittedActions(BaseModel):
    """Opt-in response mixin exposing server-resolved object-level affordances.

    ``permitted_actions`` lists the **full capability strings** (e.g.
    ``"comment:update"``, ``"comment:delete"``, ``"comment:react"``) the calling
    principal may perform on this specific object — the same vocabulary as
    ``GET /me/permissions``.

    Population is **automatic**: a subclass sets ``__resource_type__`` (the
    capability prefix, e.g. ``ResourceType.COMMENT``) and, during response
    serialization, the validator below fills ``permitted_actions`` from the
    per-request affordance context bound by
    :func:`~rhesis.backend.app.dependencies.bind_affordance_context`. A schema that
    leaves ``__resource_type__`` as ``None``, or any serialization outside a request
    (background tasks, scripts), yields an empty list — fail closed.

    ``__owner_attr__`` names the validated model's owner field used for
    ownership-gated (``:own``) actions; it defaults to ``user_id`` and is overridden
    per schema where the owner is named differently (e.g. ``owner_user_id`` for
    experiments). The field is read from the validated model, so it is reliably
    present regardless of whether the response was built from an ORM object, a
    dict, or an explicit model constructor.
    """

    # ClassVars (not model fields). Set on subclasses to opt in.
    __resource_type__: ClassVar[Optional[str]] = None
    __owner_attr__: ClassVar[str] = "user_id"

    permitted_actions: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _populate_permitted_actions(self) -> "WithPermittedActions":
        cls = type(self)
        resource_type = cls.__resource_type__
        # No opt-in, or already populated (e.g. explicit re-serialization of a model
        # whose actions were resolved on the first validation pass) → leave as-is.
        if resource_type is None or self.permitted_actions:
            return self
        # Local import: the auth layer is heavier and importing it at module load
        # would invert the schema -> auth dependency direction and risk a cycle.
        from rhesis.backend.app.auth.affordances import current_affordance_context

        ctx = current_affordance_context()
        if ctx is None:
            return self
        owner_id = getattr(self, cls.__owner_attr__, None)
        self.permitted_actions = ctx.actions_for(resource_type, owner_id)
        return self
