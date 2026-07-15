"""Server-driven authorization affordances — attach per-object permitted actions.

Affordance computation is **automatic** for ORM-backed responses: any response
schema mixing in :class:`~rhesis.backend.app.schemas.affordances.WithPermittedActions`
and declaring a ``__resource_type__`` has its ``permitted_actions`` filled during
response serialization (see that mixin's ``model_validator``). The validator reads
the per-request :class:`_AffordanceContext` bound here — there is no per-route call
to remember.

The context is bound once per request by
:func:`~rhesis.backend.app.dependencies.bind_affordance_context`, which
``main.apply_affordance_backstop`` injects on exactly the routes whose
``response_model`` carries the mixin. Capability resolution is **lazy and
memoized**: the effective capability set is computed on first use and reused for
every object in the response, so a list endpoint is a single PDP pass and a
response with no affordances pays nothing.

:func:`populate_review_permitted_actions` remains explicit: reviews are JSONB
sub-documents (plain dicts), not ORM objects routed through a Pydantic
``WithPermittedActions`` schema, so the validator never sees them.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import List, Optional
from uuid import UUID as _UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import (
    ResourceType,
    get_all_capabilities,
    permitted_actions_for,
)
from rhesis.backend.app.auth.principal import resolve_principal_from_request
from rhesis.backend.app.auth.rbac import effective_permissions, project_id_from_scope


def _own_gated_actions(resource_type: str) -> set[str]:
    """Actions of *resource_type* that have an object-level qualifier variant in the catalog.

    A ``{resource}:{action}:own`` or ``{resource}:{action}:assigned`` capability means the
    route enforces object-level ownership or assignment via ``authorize_object``, so the
    affordance must require the same — the plain cap alone (held broadly in the community
    tier) is insufficient.

    Returns a **sentinel** (``{"*"}`` — matches every action) when the capability catalog
    is not yet registered.  ``permitted_actions_for`` interprets any non-empty
    ``own_gated_actions`` set as gated for every action whose name appears in it; the
    sentinel effectively gates *all* actions for this resource, which is fail-closed:
    no plain caps are advertised on objects the caller may not own.
    """
    all_caps = get_all_capabilities()
    if not all_caps:
        # Catalog not yet registered (pre-startup scripts, some test paths).
        # Return a sentinel that causes permitted_actions_for to treat every action
        # as gated — fail-closed rather than fail-open.
        return {"*"}
    resource = str(resource_type)
    gated: set[str] = set()
    for cap in all_caps:
        parts = cap.split(":")
        if len(parts) == 3 and parts[0] == resource and parts[2] in ("own", "assigned"):
            gated.add(parts[1])
    return gated


def _owner_shim(owner_id: object, assignee_id: object = None) -> object:
    """Wrap owner and assignee ids as an object exposing ``user_id`` and ``assignee_id``.

    :func:`permitted_actions_for` reads ownership via ``obj.user_id`` and assignment
    via ``obj.assignee_id``. Affordances are computed from the validated response model,
    whose owner field name varies (``owner_user_id`` for experiments, ``user_id``
    elsewhere), so the caller extracts the ids and wraps them here rather than passing
    a heterogeneous object.
    """
    return SimpleNamespace(user_id=owner_id, assignee_id=assignee_id)


@dataclass
class _AffordanceContext:
    """Per-request holder for server-driven affordance resolution.

    Bound once per request by
    :func:`~rhesis.backend.app.dependencies.bind_affordance_context` and read by
    the :class:`WithPermittedActions` model validator during response
    serialization. Capability resolution is **lazy and memoized**: the first
    :meth:`actions_for` call resolves the principal and effective caps; every
    subsequent call (e.g. each row of a list response) reuses them.
    """

    current_user: object
    request: object
    db: Session
    #: Resource type(s) this route's response can need affordances for (derived
    #: at startup by ``main.apply_affordance_backstop``). ``None`` means check
    #: the full capability catalog.
    resource_types: Optional[frozenset] = None
    _caps: Optional[List[str]] = field(default=None, init=False)
    _principal: object = field(default=None, init=False)
    _own_gated: dict = field(default_factory=dict, init=False)

    def _ensure_caps(self) -> List[str]:
        if self._caps is None:
            self._principal = resolve_principal_from_request(self.current_user, self.request)
            project_id = project_id_from_scope(self.db)
            self._caps = effective_permissions(
                self._principal,
                project_id=project_id,
                db=self.db,
                resource_types=self.resource_types,
            )
        return self._caps

    def precompute(self) -> None:
        """Eagerly resolve the effective capability set.

        Called once by :func:`~rhesis.backend.app.dependencies.bind_affordance_context`
        before yielding to the route handler, so that the synchronous I/O (DB/Redis) for
        ``effective_permissions`` happens inside the async dependency — not lazily during
        response serialization on the event loop where blocking is harder to control.

        After this call, subsequent :meth:`actions_for` invocations (e.g. each row of a
        list response) are entirely in-memory.
        """
        self._ensure_caps()

    def actions_for(
        self, resource_type: object, owner_id: object, assignee_id: object = None
    ) -> List[str]:
        """Full capability strings the caller may exercise on an object of this type.

        *owner_id* is the object's owner (read from the validated response model);
        ownership-gated (``:own``) actions are granted only when it matches the caller.
        *assignee_id* is optional; assignment-gated (``:assigned``) actions are granted
        only when it is present and matches the caller.
        """
        caps = self._ensure_caps()
        rt = str(resource_type)
        gated = self._own_gated.get(rt)
        if gated is None:
            gated = _own_gated_actions(rt)
            self._own_gated[rt] = gated
        return permitted_actions_for(
            caps,
            _owner_shim(owner_id, assignee_id),
            resource_type,
            current_user_id=self._principal.user_id,
            own_gated_actions=gated,
        )


# Per-request affordance context. ``None`` outside a request (background tasks,
# scripts) so the validator fails closed (empty ``permitted_actions``). Bound only
# by an *async* dependency so the value lives in the request's event-loop context,
# where response serialization — and thus the validator — reads it.
_affordance_ctx: ContextVar[Optional[_AffordanceContext]] = ContextVar(
    "rhesis_affordance_ctx", default=None
)


def current_affordance_context() -> Optional[_AffordanceContext]:
    """Return the affordance context bound for the current request, or ``None``."""
    return _affordance_ctx.get()


def set_affordance_context(
    current_user: object,
    request: object,
    db: Session,
    resource_types: Optional[frozenset] = None,
) -> object:
    """Bind a fresh affordance context; returns a token for :func:`reset_affordance_context`."""
    return _affordance_ctx.set(
        _AffordanceContext(
            current_user=current_user, request=request, db=db, resource_types=resource_types
        )
    )


def reset_affordance_context(token: object) -> None:
    """Restore the affordance context to its value before the matching ``set`` call."""
    _affordance_ctx.reset(token)


def populate_review_permitted_actions(reviews: List[dict]) -> List[dict]:
    """Enrich review dicts (JSONB sub-documents) with per-review permitted_actions.

    Review dicts are stored as JSONB blobs — not ORM objects routed through a
    ``WithPermittedActions`` Pydantic schema — so the automatic validator never
    sees them. This helper reuses the per-request
    :class:`_AffordanceContext` (already bound by
    :func:`~rhesis.backend.app.dependencies.bind_affordance_context`) to project
    the caller's caps onto each review, reading ``review["user"]["user_id"]`` as
    the ownership field.

    Returns the list unchanged (and without adding keys) when no affordance context
    is bound — e.g. in background tasks or scripts.

    Mutates each dict in-place (adds ``"permitted_actions"`` key). Safe to call on
    GET handlers — the JSONB column is never auto-flushed without an explicit
    ``flag_modified`` + ``commit``.
    """
    if not reviews:
        return reviews

    ctx = current_affordance_context()
    if ctx is None:
        return reviews

    for review in reviews:
        raw_uid = review.get("user", {}).get("user_id")
        try:
            uid: _UUID | None = _UUID(str(raw_uid)) if raw_uid else None
        except (ValueError, AttributeError):
            uid = None
        review["permitted_actions"] = ctx.actions_for(ResourceType.TEST_RESULT, uid)
    return reviews
